# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import logging
import typing

from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from uds.core import auths, consts, exceptions, types
from uds.core.auths.auth import (authenticate_via_callback, log_login,
                                 uds_cookie, web_login, web_logout)
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.user_service import UserServiceManager
from uds.core.services.exceptions import ServiceNotReadyError
from uds.core.types.states import State
from uds.core.util import html
from uds.core.util.model import process_uuid
from uds.models import Authenticator, ServicePool, TicketStore
from uds.web.util import errors

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

# The callback is now a two stage, so we can use cookies samesite policy to "Lax"
# 1.- First stage:  SESSION COOKIE IS NOT PRESSENT HERE
#       * gets all parameters of callback and stores it in a ticket.
#       * Redirectos to stage2, with ticket id parameter
# 2.- Second Stage:  SESSION COOKIE IS PRESENT!!
#       * Recovers parameters from first stage
#       * Process real callback


@csrf_exempt
def auth_callback(request: HttpRequest, authenticator_name: str) -> HttpResponse:
    """
    This url is provided so external SSO authenticators can get an url for
    redirecting back the users.

    This will invoke authCallback of the requested idAuth and, if this represents
    an authenticator that has an authCallback
    """
    try:
        authenticator = (
            Authenticator.objects.filter(Q(name=authenticator_name) | Q(small_name=authenticator_name)).order_by('priority').first()
        )
        if not authenticator:
            raise Exception('Authenticator not found')

        params = types.auth.AuthCallbackParams.from_request(request)

        logger.debug('Auth callback for %s with params %s', authenticator, params)

        ticket = TicketStore.create({'params': params, 'auth': authenticator.uuid})
        return HttpResponseRedirect(reverse('page.auth.callback_stage2', args=[ticket]))
    except Exception as e:
        # No authenticator found...
        return errors.exception_view(request, e)


def auth_callback_stage2(request: 'ExtendedHttpRequestWithUser', ticket_id: str) -> HttpResponse:
    try:
        ticket = TicketStore.get(ticket_id, invalidate=True)
        params: types.auth.AuthCallbackParams = ticket['params']
        auth_uuid: str = ticket['auth']
        authenticator = Authenticator.objects.get(uuid=auth_uuid)

        result = authenticate_via_callback(authenticator, params, request)

        if result.url:
            raise exceptions.auth.Redirect(result.url)

        if result.user is None:
            log_login(request, authenticator, f'{params}', 'Invalid at auth callback')
            raise exceptions.auth.InvalidUserException()

        response = HttpResponseRedirect(reverse('page.index'))

        web_login(request, response, result.user, '')  # Password is unavailable in this case

        log_login(request, authenticator, result.user.name, 'Federated login')

        # If MFA is provided, we need to redirect to MFA page
        request.authorized = True
        if authenticator.get_type().provides_mfa() and authenticator.mfa:
            authInstance = authenticator.get_instance()
            if authInstance.mfa_identifier(result.user.name):
                request.authorized = False  # We can ask for MFA so first disauthorize user
                response = HttpResponseRedirect(reverse('page.mfa'))

        return response
    except exceptions.auth.Redirect as e:
        return HttpResponseRedirect(request.build_absolute_uri(str(e)) if e.args and e.args[0] else '/')
    except exceptions.auth.Logout as e:
        return web_logout(
            request,
            request.build_absolute_uri(str(e)) if e.args and e.args[0] else None,
        )
    except Exception as e:
        logger.exception('authCallback')
        return errors.exception_view(request, e)


@csrf_exempt
def auth_info(request: 'HttpRequest', authenticator_name: str) -> HttpResponse:
    """
    This url is provided so authenticators can provide info (such as SAML metadata)

    This will invoke getInfo on requested authName. The search of the authenticator is done
    by name, so it's easier to access from external sources
    """
    try:
        logger.debug('Getting info for %s', authenticator_name)
        authenticator = (
            Authenticator.objects.filter(Q(name=authenticator_name) | Q(small_name=authenticator_name)).order_by('priority').first()
        )
        if not authenticator:
            raise Exception('Authenticator not found')
        authInstance = authenticator.get_instance()
        if typing.cast(typing.Any, authInstance.get_info) == auths.Authenticator.get_info:
            raise Exception()  # This authenticator do not provides info

        info = authInstance.get_info(request.GET)

        if info is None:
            raise Exception()  # This auth do not provides info

        infoContent = info[0]
        infoType = info[1] or 'text/html'

        return HttpResponse(infoContent, content_type=infoType)
    except Exception:
        logger.exception('got')
        return HttpResponse(_('Authenticator does not provide information'))


# Gets the javascript from the custom authtenticator
@never_cache
def custom_auth(request: 'HttpRequest', auth_id: str) -> HttpResponse:
    res: typing.Optional[str] = ''
    try:
        try:
            auth = Authenticator.objects.get(uuid=process_uuid(auth_id))
        except Authenticator.DoesNotExist:
            auth = Authenticator.objects.get(pk=auth_id)
        res = auth.get_instance().get_javascript(request)
        if not res:
            res = ''
    except Exception:
        logger.exception('customAuth')
        res = 'error'
    return HttpResponse(res, content_type='text/javascript')


@never_cache
def ticket_auth(
    request: 'ExtendedHttpRequestWithUser', ticket_id: str
) -> HttpResponse:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """
    Used to authenticate an user via a ticket
    """
    try:
        data = TicketStore.get(ticket_id, invalidate=True)

        try:
            # Extract ticket.data from ticket.data storage, and remove it if success
            username = data['username']
            groups = data['groups']
            auth = data['auth']
            realname = data['realname']
            poolUuid = data['servicePool']
            password = CryptoManager().decrypt(data['password'])
        except Exception:
            logger.error('Ticket stored is not valid')
            raise exceptions.auth.InvalidUserException() from None

        auth = Authenticator.objects.get(uuid=auth)
        # If user does not exists in DB, create it right now
        # Add user to groups, if they exists...
        grps: list = []
        for g in groups:
            try:
                grps.append(auth.groups.get(uuid=g))
            except Exception:
                logger.debug('Group list has changed since ticket assignment')

        if not grps:
            logger.error('Ticket has no valid groups')
            raise Exception('Invalid ticket authentication')

        usr = auth.get_or_create_user(username, realname)
        if usr is None or State.from_str(usr.state).is_active() is False:  # If user is inactive, raise an exception
            raise exceptions.auth.InvalidUserException()

        # Add groups to user (replace existing groups)
        usr.groups.set(grps)  # type: ignore

        # Force cookie generation
        web_login(request, None, usr, password)

        # Log the login
        log_login(request, auth, username, 'Ticket authentication')

        request.user = (
            usr  # Temporarily store this user as "authenticated" user, next requests will be done using session
        )
        request.authorized = True  # User is authorized

        # Set restricted access (no allow to see other services, logout automatically if user tries to access other service, ...)
        request.session['restricted'] = True  # Access is from ticket

        # Transport must always be automatic for ticket authentication

        logger.debug("Service & transport: %s", poolUuid)

        # Check if servicePool is part of the ticket
        if poolUuid:
            # Request service, with transport = None so it is automatic
            res = UserServiceManager().get_user_service_info(
                request.user, request.os, request.ip, poolUuid, None, False
            )
            _, userservice, _, transport, _ = res

            transportInstance = transport.get_instance()
            if transportInstance.own_link is True:
                link = reverse(
                    'webapi.transport_own_link', args=('A' + userservice.uuid, transport.uuid)  # type: ignore
                )
            else:
                link = html.uds_access_link(request, 'A' + userservice.uuid, transport.uuid)  # type: ignore

            request.session['launch'] = link
            response = HttpResponseRedirect(reverse('page.ticket.launcher'))
        else:
            response = HttpResponseRedirect(reverse('page.index'))

        # Now ensure uds cookie is at response
        uds_cookie(request, response, True)
        return response
    except ServiceNotReadyError:
        return errors.error_view(request, types.errors.Error.SERVICE_NOT_READY)
    except TicketStore.InvalidTicket:
        return errors.error_view(request, types.errors.Error.RELOAD_NOT_SUPPORTED)
    except Authenticator.DoesNotExist:
        logger.error('Ticket has an non existing authenticator')
        return errors.error_view(request, types.errors.Error.ACCESS_DENIED)
    except ServicePool.DoesNotExist:  # type: ignore  # DoesNotExist is different for each model
        logger.error('Ticket has an invalid Service Pool')
        return errors.error_view(request, types.errors.Error.SERVICE_NOT_FOUND)
    except Exception as e:
        logger.exception('Exception')
        return errors.exception_view(request, e)
