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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import logging
import typing

from django.urls import reverse
from django.db.models import Q
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

import uds.web.util.errors as errors
from uds.core import auths
from uds.core.auths.auth import (
    webLogin,
    webLogout,
    authenticateViaCallback,
    authLogLogin,
    getUDSCookie,
)
from uds.core.managers import userServiceManager, cryptoManager
from uds.core.services.exceptions import ServiceNotReadyError
from uds.core.util import os_detector as OsDetector
from uds.core.util import html
from uds.core.util.state import State
from uds.core.util.model import processUuid
from uds.models import Authenticator, ServicePool
from uds.models import TicketStore

if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

# The callback is now a two stage, so we can use cookies samesite policy to "Lax"
# 1.- First stage:  SESSION COOKIE IS NOT PRESSENT HERE
#       * gets all parameters of callback and stores it in a ticket.
#       * Redirectos to stage2, with ticket id parameter
# 2.- Second Stage:  SESSION COOKIE IS PRESENT!!
#       * Recovers parameters from first stage
#       * Process real callback


@csrf_exempt
def authCallback(request: 'ExtendedHttpRequestWithUser', authName: str) -> HttpResponse:
    """
    This url is provided so external SSO authenticators can get an url for
    redirecting back the users.

    This will invoke authCallback of the requested idAuth and, if this represents
    an authenticator that has an authCallback
    """
    try:
        authenticator = Authenticator.objects.filter(Q(name=authName) | Q(small_name=authName)).order_by('priority').first()
        if not authenticator:
            raise Exception('Authenticator not found')

        params = {
            'https': request.is_secure(),
            'http_host': request.META['HTTP_HOST'],
            'path_info': request.META['PATH_INFO'],
            'server_port': request.META['SERVER_PORT'],
            'get_data': request.GET.copy(),
            'post_data': request.POST.copy(),
            'query_string': request.META['QUERY_STRING'],
        }

        logger.debug(
            'Auth callback for %s with params %s', authenticator, params.keys()
        )

        ticket = TicketStore.create({'params': params, 'auth': authenticator.uuid})
        return HttpResponseRedirect(reverse('page.auth.callback_stage2', args=[ticket]))
    except Exception as e:
        # No authenticator found...
        return errors.exceptionView(request, e)


def authCallback_stage2(
    request: 'ExtendedHttpRequestWithUser', ticketId: str
) -> HttpResponse:
    try:
        ticket = TicketStore.get(ticketId)
        params: typing.Dict[str, typing.Any] = ticket['params']
        auth_uuid: str = ticket['auth']
        authenticator = Authenticator.objects.get(uuid=auth_uuid)

        result = authenticateViaCallback(authenticator, params, request)

        os = OsDetector.getOsFromUA(request.META['HTTP_USER_AGENT'])

        if result.url:
            raise auths.exceptions.Redirect(result.url)

        if result.user is None:
            authLogLogin(
                request, authenticator, '{0}'.format(params), 'Invalid at auth callback'
            )
            raise auths.exceptions.InvalidUserException()

        response = HttpResponseRedirect(reverse('page.index'))

        webLogin(request, response, result.user, '')  # Password is unavailable in this case
        request.session['OS'] = os
        # Now we render an intermediate page, so we get Java support from user
        # It will only detect java, and them redirect to Java

        return response
    except auths.exceptions.Redirect as e:
        return HttpResponseRedirect(
            request.build_absolute_uri(str(e)) if e.args and e.args[0] else '/'
        )
    except auths.exceptions.Logout as e:
        return webLogout(
            request,
            request.build_absolute_uri(str(e)) if e.args and e.args[0] else None,
        )
    except Exception as e:
        logger.exception('authCallback')
        return errors.exceptionView(request, e)

    # Will never reach this
    raise RuntimeError('Unreachable point reached!!!')


@csrf_exempt
def authInfo(request: 'HttpRequest', authName: str) -> HttpResponse:
    """
    This url is provided so authenticators can provide info (such as SAML metadata)

    This will invoke getInfo on requested authName. The search of the authenticator is done
    by name, so it's easier to access from external sources
    """
    try:
        logger.debug('Getting info for %s', authName)
        authenticator = Authenticator.objects.get(name=authName)
        authInstance = authenticator.getInstance()
        if typing.cast(typing.Any, authInstance.getInfo) == auths.Authenticator.getInfo:
            raise Exception()  # This authenticator do not provides info

        info = authInstance.getInfo(request.GET)

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
def customAuth(request: 'HttpRequest', idAuth: str) -> HttpResponse:
    res = ''
    try:
        try:
            auth = Authenticator.objects.get(uuid=processUuid(idAuth))
        except Authenticator.DoesNotExist:
            auth = Authenticator.objects.get(pk=idAuth)
        res = auth.getInstance().getJavascript(request)
        if not res:
            res = ''
    except Exception:
        logger.exception('customAuth')
        res = 'error'
    return HttpResponse(res, content_type='text/javascript')


@never_cache
def ticketAuth(
    request: 'ExtendedHttpRequestWithUser', ticketId: str
) -> HttpResponse:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """
    Used to authenticate an user via a ticket
    """
    try:
        data = TicketStore.get(ticketId, invalidate=True)

        try:
            # Extract ticket.data from ticket.data storage, and remove it if success
            username = data['username']
            groups = data['groups']
            auth = data['auth']
            realname = data['realname']
            poolUuid = data['servicePool']
            password = cryptoManager().decrypt(data['password'])
        except Exception:
            logger.error('Ticket stored is not valid')
            raise auths.exceptions.InvalidUserException()

        auth = Authenticator.objects.get(uuid=auth)
        # If user does not exists in DB, create it right now
        # Add user to groups, if they exists...
        grps: typing.List = []
        for g in groups:
            try:
                grps.append(auth.groups.get(uuid=g))
            except Exception:
                logger.debug('Group list has changed since ticket assignment')

        if not grps:
            logger.error('Ticket has no valid groups')
            raise Exception('Invalid ticket authentication')

        usr = auth.getOrCreateUser(username, realname)
        if (
            usr is None or State.isActive(usr.state) is False
        ):  # If user is inactive, raise an exception
            raise auths.exceptions.InvalidUserException()

        # Add groups to user (replace existing groups)
        usr.groups.set(grps)  # type: ignore

        # Force cookie generation
        webLogin(request, None, usr, password)

        request.user = usr  # Temporarily store this user as "authenticated" user, next requests will be done using session
        request.session['ticket'] = '1'  # Store that user access is done using ticket

        # Transport must always be automatic for ticket authentication

        logger.debug("Service & transport: %s", poolUuid)

        # Check if servicePool is part of the ticket
        if poolUuid:
            # Request service, with transport = None so it is automatic
            res = userServiceManager().getService(
                request.user, request.os, request.ip, poolUuid, None, False
            )
            _, userService, _, transport, _ = res

            transportInstance = transport.getInstance()
            if transportInstance.ownLink is True:
                link = reverse(
                    'TransportOwnLink', args=('A' + userService.uuid, transport.uuid)
                )
            else:
                link = html.udsAccessLink(
                    request, 'A' + userService.uuid, transport.uuid
                )

            request.session['launch'] = link
            response = HttpResponseRedirect(reverse('page.ticket.launcher'))
        else:
            response = HttpResponseRedirect(reverse('page.index'))

        # Now ensure uds cookie is at response
        getUDSCookie(request, response, True)
        return response
    except ServiceNotReadyError as e:
        return errors.errorView(request, errors.SERVICE_NOT_READY)
    except TicketStore.InvalidTicket:
        return errors.errorView(request, errors.RELOAD_NOT_SUPPORTED)
    except Authenticator.DoesNotExist:
        logger.error('Ticket has an non existing authenticator')
        return errors.errorView(request, errors.ACCESS_DENIED)
    except ServicePool.DoesNotExist:  # type: ignore  # DoesNotExist is different for each model
        logger.error('Ticket has an invalid Service Pool')
        return errors.errorView(request, errors.SERVICE_NOT_FOUND)
    except Exception as e:
        logger.exception('Exception')
        return errors.exceptionView(request, e)
