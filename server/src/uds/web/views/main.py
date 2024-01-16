# -*- coding: utf-8 -*-
#
# Copyright (c) 2018-2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import datetime
import json
import logging
import random
import time
import typing

from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.middleware import csrf
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from uds import models
from uds.core import consts, exceptions, mfas, types
from uds.core.auths import auth
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.user_service import UserServiceManager
from uds.core.util import config, storage
from uds.core.util.model import sql_stamp_seconds
from uds.web.forms.login_form import LoginForm
from uds.web.forms.mfa_form import MFAForm
from uds.web.util import configjs, errors
from uds.web.util.authentication import check_login
from uds.web.util.services import get_services_info_dict

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    pass


@never_cache
def index(request: HttpRequest) -> HttpResponse:
    # Gets csrf token
    csrf_token = csrf.get_token(request)
    if csrf_token is not None:
        csrf_token = str(csrf_token)

    response = render(
        request=request,
        template_name='uds/modern/index.html',
        context={'csrf_field': consts.auth.CSRF_FIELD, 'csrf_token': csrf_token},
    )

    # Ensure UDS cookie is present
    auth.uds_cookie(request, response)

    return response


# Includes a request.session ticket, indicating that
@never_cache
def ticket_launcher(request: HttpRequest) -> HttpResponse:
    return index(request)


# Basically, the original /login method, but fixed for modern interface
@never_cache
def login(request: types.requests.ExtendedHttpRequest, tag: typing.Optional[str] = None) -> HttpResponse:
    # Default empty form
    tag = tag or request.session.get('tag', None)

    logger.debug('Tag: %s', tag)
    response: typing.Optional[HttpResponse] = None
    if request.method == 'POST':
        request.session['restricted'] = False  # Access is from login
        request.authorized = False  # Ensure that on login page, user is unauthorized first

        form = LoginForm(request.POST, tag=tag)
        loginResult = check_login(request, form, tag)
        if loginResult.user:
            response = HttpResponseRedirect(reverse('page.index'))
            # save tag, weblogin will clear session
            tag = request.session.get('tag')
            auth.web_login(
                request, response, loginResult.user, loginResult.password
            )  # data is user password here

            # If MFA is provided, we need to redirect to MFA page
            request.authorized = True
            if (
                loginResult.user.manager.get_type().provides_mfa()
                and loginResult.user.manager.mfa
                and loginResult.user.groups.filter(skip_mfa=types.states.State.ACTIVE).count() == 0
            ):
                request.authorized = False
                response = HttpResponseRedirect(reverse('page.mfa'))

        else:
            # If redirection on login failure is found, honor it
            if loginResult.url:  # Redirection
                return HttpResponseRedirect(loginResult.url)

            if request.ip not in ('127.0.0.1', '::1'):  # If not localhost, wait a bit
                time.sleep(
                    random.SystemRandom().randint(1600, 2400) / 1000
                )  # On failure, wait a bit if not localhost (random wait)
            # If error is numeric, redirect...
            if loginResult.errid:
                return errors.error_view(request, loginResult.errid)

            # Error, set error on session for process for js
            request.session['errors'] = [loginResult.errstr]
    else:
        request.session['tag'] = tag

    return response or index(request)


@never_cache
@auth.web_login_required(admin=False)
def logout(request: types.requests.ExtendedHttpRequestWithUser) -> HttpResponse:
    auth.log_logout(request)
    request.session['restricted'] = False  # Remove restricted
    request.authorized = False
    logoutResponse = request.user.logout(request)
    url = logoutResponse.url if logoutResponse.success == types.auth.AuthenticationState.REDIRECT else None

    return auth.web_logout(request, url or request.session.get('logouturl', None))


@never_cache
def js(request: types.requests.ExtendedHttpRequest) -> HttpResponse:
    return HttpResponse(content=configjs.uds_js(request), content_type='application/javascript')


@never_cache
@auth.deny_non_authenticated  # web_login_required not used here because this is not a web page, but js
def services_data_json(request: types.requests.ExtendedHttpRequestWithUser) -> HttpResponse:
    return JsonResponse(get_services_info_dict(request))


# The MFA page does not needs CSRF token, so we disable it
@csrf_exempt
def mfa(
    request: types.requests.ExtendedHttpRequest,
) -> HttpResponse:  # pylint: disable=too-many-return-statements,too-many-statements
    if not request.user or request.authorized:  # If no user, or user is already authorized, redirect to index
        logger.warning('MFA: No user or user is already authorized')
        return HttpResponseRedirect(reverse('page.index'))  # No user, no MFA

    store: 'storage.Storage' = storage.Storage('mfs')

    mfa_provider = typing.cast('None|models.MFA', request.user.manager.mfa)
    if not mfa_provider:
        logger.warning('MFA: No MFA provider for user')
        return HttpResponseRedirect(reverse('page.index'))

    mfa_user_id = mfas.MFA.get_user_id(request.user)

    # Try to get cookie anc check it
    mfa_cookie = request.COOKIES.get(consts.auth.MFA_COOKIE_NAME, None)
    if mfa_cookie and mfa_provider.remember_device > 0:
        stored_user_id: typing.Optional[str]
        created: typing.Optional[datetime.datetime]
        stored_user_id, created = store.get_unpickle(mfa_cookie) or (None, None)
        if (
            stored_user_id
            and created
            and created + datetime.timedelta(hours=mfa_provider.remember_device) > datetime.datetime.now()
        ):
            # Cookie is valid, skip MFA setting authorization
            logger.debug('MFA: Cookie is valid, skipping MFA')
            request.authorized = True
            return HttpResponseRedirect(reverse('page.index'))

    # Obtain MFA data
    auth_instance = request.user.manager.get_instance()
    mfa_instance = typing.cast('mfas.MFA', mfa_provider.get_instance())

    # Get validity duration
    validity = mfa_provider.validity * 60
    now = sql_stamp_seconds()
    start_time = request.session.get('mfa_start_time', now)

    # If mfa process timed out, we need to start login again
    if 0 < validity < now - start_time:
        logger.debug('MFA: MFA process timed out')
        request.session.flush()  # Clear session, and redirect to login
        return HttpResponseRedirect(reverse('page.login'))

    mfa_identifier = auth_instance.mfa_identifier(request.user.name)
    label = mfa_instance.label()

    if not mfa_identifier:
        allow_login_without_identifier = mfa_instance.allow_login_without_identifier(request)
        # can be True, False or None
        if allow_login_without_identifier is True:
            # Allow login
            request.authorized = True
            return HttpResponseRedirect(reverse('page.index'))
        if allow_login_without_identifier is False:
            # Not allowed to login, redirect to login error page
            logger.warning(
                'MFA identifier not found for user %s on authenticator %s. It is required by MFA %s',
                request.user.name,
                request.user.manager.name,
                mfa_provider.name,
            )
            return errors.error_view(request, types.errors.Error.ACCESS_DENIED)
        # None, the authenticator will decide what to do if mfa_identifier is empty

    tries = request.session.get('mfa_tries', 0)
    if request.method == 'POST':  # User has provided MFA code
        form = MFAForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            try:
                mfa_instance.validate(
                    request,
                    mfa_user_id,
                    request.user.name,
                    mfa_identifier,
                    code,
                    validity=validity,
                )  # Will raise MFAError if code is not valid
                request.authorized = True
                # Remove mfa_start_time and mfa from session
                for i in ('mfa_start_time', 'mfa'):
                    if i in request.session:
                        del request.session[i]

                # Redirect to index by default
                response = HttpResponseRedirect(reverse('page.index'))

                # If mfaProvider requests to keep MFA code on client, create a mfacookie for this user
                if mfa_provider.remember_device > 0 and form.cleaned_data['remember'] is True:
                    # Store also cookie locally, to check if remember_device is changed
                    mfa_cookie = CryptoManager().random_string(96)
                    store.put_pickle(
                        mfa_cookie,
                        (mfa_user_id, now),
                    )
                    response.set_cookie(
                        consts.auth.MFA_COOKIE_NAME,
                        mfa_cookie,
                        max_age=mfa_provider.remember_device * 60 * 60,
                    )

                return response
            except exceptions.auth.MFAError as e:
                logger.error('MFA error: %s', e)
                tries += 1
                request.session['mfa_tries'] = tries
                if tries >= config.GlobalConfig.MAX_LOGIN_TRIES.as_int():
                    # Clean session
                    request.session.flush()
                    # Too many tries, redirect to login error page
                    return errors.error_view(request, types.errors.Error.ACCESS_DENIED)
                return errors.error_view(request, types.errors.Error.INVALID_MFA_CODE)
        else:
            pass  # Will render again the page
    else:
        # Make MFA send a code
        request.session['mfa_tries'] = 0  # Reset tries
        try:
            result = mfa_instance.process(
                request,
                mfa_user_id,
                request.user.name,
                mfa_identifier,
                validity=validity,
            )
            if result == mfas.MFA.RESULT.ALLOWED:
                # MFA not needed, redirect to index after authorization of the user
                request.authorized = True
                return HttpResponseRedirect(reverse('page.index'))

            # store on session the start time of the MFA process if not already stored
            if 'mfa_start_time' not in request.session:
                request.session['mfa_start_time'] = now
        except Exception as e:
            logger.error('Error processing MFA: %s', e)
            return errors.error_view(request, types.errors.Error.UNKNOWN_ERROR)

    # Compose a nice "XX years, XX months, XX days, XX hours, XX minutes" string from mfaProvider.remember_device
    remember_device = ''
    # Remember_device is in hours
    if mfa_provider.remember_device > 0:
        # if more than a day, we show days only
        if mfa_provider.remember_device >= 24:
            remember_device = _('{} days').format(mfa_provider.remember_device // 24)
        else:
            remember_device = _('{} hours').format(mfa_provider.remember_device)

    # Html from MFA provider
    mfa_html = mfa_instance.html(request, mfa_user_id, request.user.name)

    # Redirect to index, but with MFA data
    request.session['mfa'] = {
        'label': label or _('MFA Code'),
        'validity': validity if validity >= 0 else 0,
        'remember_device': remember_device,
        'html': mfa_html,
    }
    return index(request)  # Render index with MFA data


@csrf_exempt
@auth.deny_non_authenticated
def update_transport_ticket(
    request: types.requests.ExtendedHttpRequestWithUser, ticket_id: str, scrambler: str
) -> HttpResponse:
    try:
        if request.method == 'POST':
            # Get request body as json
            data: dict[str, str] = json.loads(request.body)

            # Update username andd password in ticket
            username = data.get('username', None) or None  # None if not present
            password: 'str|bytes|None' = (
                data.get('password', None) or None
            )  # If password is empty, set it to None
            domain = data.get('domain', None) or None  # If empty string, set to None

            if password:
                password = CryptoManager().symmetric_encrypt(password, scrambler)

            def _is_ticket_valid(data: collections.abc.Mapping[str, typing.Any]) -> bool:
                if 'ticket-info' in data:
                    try:
                        user = models.User.objects.get(
                            uuid=typing.cast(dict[str, str], data['ticket-info']).get('user', None)
                        )
                        if request.user != user:
                            return False
                    except models.User.DoesNotExist:
                        return False

                    if username:
                        try:
                            userService = models.UserService.objects.get(
                                uuid=data['ticket-info'].get('userService', None)
                            )
                            UserServiceManager().notify_preconnect(
                                userService,
                                types.connections.ConnectionData(
                                    username=username,
                                    protocol=data.get('protocol', ''),
                                    service_type=data['ticket-info'].get('service_type', ''),
                                ),
                            )
                        except models.UserService.DoesNotExist:
                            pass

                return True

            models.TicketStore.update(
                uuid=ticket_id,
                checkFnc=_is_ticket_valid,
                username=username,
                password=password,
                domain=domain,
            )
            return HttpResponse('{"status": "OK"}', status=200, content_type='application/json')
    except Exception as e:
        # fallback to error
        logger.warning('Error updating ticket: %s', e)

    # Invalid request
    return HttpResponse('{"status": "Invalid Request"}', status=400, content_type='application/json')
