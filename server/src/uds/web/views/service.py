# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
import json
import logging
import typing

from django.utils.translation import ugettext as _
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.cache import cache_page, never_cache

from uds.core.auths.auth import webLoginRequired, webPassword
from uds.core.managers import userServiceManager, cryptoManager
from uds.models import TicketStore
from uds.core.ui.images import DEFAULT_IMAGE
from uds.core.util.model import processUuid
from uds.models import Transport, Image
from uds.core.util import html, log
from uds.core.services.exceptions import (
    ServiceNotReadyError,
    MaxServicesReachedError,
    ServiceAccessDeniedByCalendar,
)

from uds.web.util import errors
from uds.web.util import services

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest, ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


@webLoginRequired(admin=False)
def transportOwnLink(
    request: 'ExtendedHttpRequestWithUser', idService: str, idTransport: str
):
    response: typing.MutableMapping[str, typing.Any] = {}

    # For type checkers to "be happy"
    try:
        res = userServiceManager().getService(
            request.user, request.os, request.ip, idService, idTransport
        )
        ip, userService, iads, trans, itrans = res  # pylint: disable=unused-variable
        # This returns a response object in fact
        if itrans and ip:
            response = {
                'url': itrans.getLink(
                    userService,
                    trans,
                    ip,
                    request.os,
                    request.user,
                    webPassword(request),
                    request,
                )
            }
    except ServiceNotReadyError as e:
        response = {'running': e.code * 25}
    except Exception as e:
        logger.exception("Exception")
        response = {'error': str(e)}

    return HttpResponse(content=json.dumps(response), content_type='application/json')

    # Will never reach this
    return errors.errorView(request, errors.UNKNOWN_ERROR)


@cache_page(3600, key_prefix='img', cache='memory')
def transportIcon(request: 'ExtendedHttpRequest', idTrans: str) -> HttpResponse:
    try:
        transport: Transport = Transport.objects.get(uuid=processUuid(idTrans))
        return HttpResponse(transport.getInstance().icon(), content_type='image/png')
    except Exception:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')


@cache_page(3600, key_prefix='img', cache='memory')
def serviceImage(request: 'ExtendedHttpRequest', idImage: str) -> HttpResponse:
    try:
        icon = Image.objects.get(uuid=processUuid(idImage))
        return icon.imageResponse()
    except Image.DoesNotExist:
        pass  # Tries to get image from transport

    try:
        transport: Transport = Transport.objects.get(uuid=processUuid(idImage))
        return HttpResponse(transport.getInstance().icon(), content_type='image/png')
    except Exception:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')


@webLoginRequired(admin=False)
@never_cache
def userServiceEnabler(
    request: 'ExtendedHttpRequestWithUser', idService: str, idTransport: str
) -> HttpResponse:
    # Maybe we could even protect this even more by limiting referer to own server /? (just a meditation..)
    logger.debug('idService: %s, idTransport: %s', idService, idTransport)
    url = ''
    error = _('Service not ready. Please, try again in a while.')

    # If meta service, process and rebuild idService & idTransport

    try:
        res = userServiceManager().getService(
            request.user, request.os, request.ip, idService, idTransport, doTest=False
        )
        scrambler = cryptoManager().randomString(32)
        password = cryptoManager().symCrypt(webPassword(request), scrambler)

        userService, trans = res[1], res[3]

        typeTrans = trans.getType()

        error = ''  # No error

        if typeTrans.ownLink:
            url = reverse('TransportOwnLink', args=('A' + userService.uuid, trans.uuid))
        else:
            data = {
                'service': 'A' + userService.uuid,
                'transport': trans.uuid,
                'user': request.user.uuid,
                'password': password,
            }

            ticket = TicketStore.create(data)
            url = html.udsLink(request, ticket, scrambler)
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        # error += ' (code {0:04X})'.format(e.code)
        error = _(
            'Your service is being created, please, wait for a few seconds while we complete it.)'
        ) + '({}%)'.format(int(e.code * 25))
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "%s"', idService)
        error = errors.errorString(errors.MAX_SERVICES_REACHED)
    except ServiceAccessDeniedByCalendar:
        logger.info('Access tried to a calendar limited access pool "%s"', idService)
        error = errors.errorString(errors.SERVICE_CALENDAR_DENIED)
    except Exception as e:
        logger.exception('Error')
        error = str(e)

    return HttpResponse(
        json.dumps({'url': str(url), 'error': str(error)}),
        content_type='application/json',
    )


def closer(request: 'ExtendedHttpRequest') -> HttpResponse:
    return HttpResponse('<html><body onload="window.close()"></body></html>')


@webLoginRequired(admin=False)
@never_cache
def action(
    request: 'ExtendedHttpRequestWithUser', idService: str, actionString: str
) -> HttpResponse:
    userService = userServiceManager().locateUserService(
        request.user, idService, create=False
    )
    response: typing.Any = None
    rebuild: bool = False
    if userService:
        if (
            actionString == 'release'
            and userService.deployed_service.allow_users_remove
        ):
            rebuild = True
            log.doLog(
                userService.deployed_service,
                log.INFO,
                "Removing User Service {} as requested by {} from {}".format(
                    userService.friendly_name, request.user.pretty_name, request.ip
                ),
                log.WEB,
            )
            userServiceManager().requestLogoff(userService)
            userService.release()
        elif (
            actionString == 'reset'
            and userService.deployed_service.allow_users_reset
            and userService.deployed_service.service.getType().canReset
        ):
            rebuild = True
            log.doLog(
                userService.deployed_service,
                log.INFO,
                "Reseting User Service {} as requested by {} from {}".format(
                    userService.friendly_name, request.user.pretty_name, request.ip
                ),
                log.WEB,
            )
            # userServiceManager().requestLogoff(userService)
            userServiceManager().reset(userService)

    if rebuild:
        # Rebuild services data, but return only "this" service
        for v in services.getServicesData(request)['services']:
            if v['id'] == idService:
                response = v
                break

    return HttpResponse(json.dumps(response), content_type="application/json")
