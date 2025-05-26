# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import typing

from uds.core import consts, exceptions, mfas, types
from uds.core.managers.crypto import CryptoManager
from uds.core.util import config, storage
from uds.core.util.model import sql_stamp_seconds
from uds.web.forms.mfa_form import MFAForm
from uds.web.util import errors
from uds.web.views.main import index, logger


from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt


import datetime


# The MFA page does not needs CSRF token, so we disable it
@csrf_exempt
def mfa(
    request: types.requests.ExtendedHttpRequest,
) -> HttpResponse:  # pylint: disable=too-many-return-statements,too-many-statements
    if not request.user or request.authorized:  # If no user, or user is already authorized, redirect to index
        logger.warning('MFA: No user or user is already authorized')
        return HttpResponseRedirect(reverse('page.index'))  # No user, no MFA

    store: 'storage.Storage' = storage.Storage('mfs')

    mfa_provider = request.user.manager.mfa  # Get MFA provider for user
    if not mfa_provider:
        logger.warning('MFA: No MFA provider for user')
        return HttpResponseRedirect(reverse('page.index'))

    mfa_user_id = mfas.MFA.get_user_unique_id(request.user)

    # Try to get cookie anc check it
    mfa_cookie = request.COOKIES.get(consts.auth.MFA_COOKIE_NAME, None)
    if mfa_cookie and mfa_provider.remember_device > 0:
        stored_user_id: typing.Optional[str]
        created: typing.Optional[int]
        stored_data = store.read_pickled(mfa_cookie) or (None, None, None)
        stored_user_id, created, ip = (stored_data + (None,))[:3]
        if (
            stored_user_id
            and created
            and (
                datetime.datetime.fromtimestamp(created)
                + datetime.timedelta(hours=mfa_provider.remember_device)
            )
            > datetime.datetime.now()
            # Old stored values do not have ip, so we need to check it
            and (not ip or ip == request.ip)
        ):
            # Cookie is valid, skip MFA setting authorization
            logger.debug('MFA: Cookie is valid, skipping MFA')
            request.authorized = True
            return HttpResponseRedirect(reverse('page.index'))

    # Obtain MFA data
    auth_instance = request.user.manager.get_instance()
    mfa_instance = mfa_provider.get_instance()

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
                    store.save_pickled(
                        mfa_cookie,
                        (mfa_user_id, now, request.ip),  # MFA will only be valid for this user and this ip
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
            except Exception as e:
                logger.error('Error processing MFA: %s', e)
                return errors.error_view(request, types.errors.Error.UNKNOWN_ERROR)
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
