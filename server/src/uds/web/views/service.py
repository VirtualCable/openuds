# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 Virtual Cable S.L.
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
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.views.decorators.cache import cache_page, never_cache

from uds.core.auths.auth import webLoginRequired, webPassword
from uds.core.services.Exceptions import ServiceInMaintenanceMode, InvalidServiceException
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.models import TicketStore
from uds.core.ui.images import DEFAULT_IMAGE
from uds.core.ui import theme
from uds.core.util.Config import GlobalConfig
from uds.core.util.stats import events
from uds.core.util import log
from uds.core.util import OsDetector
from uds.models import DeployedService, Transport, UserService, Image
from uds.core.util import html

import uds.web.errors as errors
from uds.core.managers import cryptoManager

import six
import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-04-26'


def getService(request, idService, idTransport, doTest=True):
    kind, idService = idService[0], idService[1:]

    logger.debug('Kind of service: {0}, idService: {1}'.format(kind, idService))
    if kind == 'A':  # This is an assigned service
        logger.debug('Getting A service {}'.format(idService))
        userService = UserService.objects.get(uuid=idService)
        userService.deployed_service.validateUser(request.user)
    else:
        ds = DeployedService.objects.get(uuid=idService)
        # We first do a sanity check for this, if the user has access to this service
        # If it fails, will raise an exception
        ds.validateUser(request.user)
        # Now we have to locate an instance of the service, so we can assign it to user.
        userService = UserServiceManager.manager().getAssignationForUser(ds, request.user)

    if userService.isInMaintenance() is True:
        raise ServiceInMaintenanceMode()

    logger.debug('Found service: {0}'.format(userService))
    trans = Transport.objects.get(uuid=idTransport)

    # Ensures that the transport is allowed for this service
    if trans not in userService.deployed_service.transports.all():
        raise InvalidServiceException()

    # If transport is not available for the request IP...
    if trans.validForIp(request.ip) is False:
        raise InvalidServiceException()

    if doTest is False:
        return (None, userService, None, trans, None)

    # Test if the service is ready
    if userService.isReady():
        log.doLog(userService, log.INFO, "User {0} from {1} has initiated access".format(request.user.name, request.ip), log.WEB)
        # If ready, show transport for this service, if also ready ofc
        iads = userService.getInstance()
        ip = iads.getIp()
        events.addEvent(userService.deployed_service, events.ET_ACCESS, username=request.user.name, srcip=request.ip, dstip=ip, uniqueid=userService.unique_id)
        if ip is not None:
            itrans = trans.getInstance()
            if itrans.isAvailableFor(ip):
                userService.setConnectionSource(request.ip, 'unknown')
                log.doLog(userService, log.INFO, "User service ready", log.WEB)
                UserServiceManager.manager().notifyPreconnect(userService, itrans.processedUser(userService, request.user), itrans.protocol)
                return (ip, userService, iads, trans, itrans)
            else:
                log.doLog(userService, log.WARN, "User service is not accessible (ip {0})".format(ip), log.TRANSPORT)
                logger.debug('Transport is not ready for user service {0}'.format(userService))
        else:
            logger.debug('Ip not available from user service {0}'.format(userService))
    else:
        log.doLog(userService, log.WARN, "User {0} from {1} tried to access, but machine was not ready".format(request.user.name, request.ip), log.WEB)

    return None


@webLoginRequired(admin=False)
def transportOwnLink(request, idService, idTransport):
    try:
        res = getService(request, idService, idTransport)
        if res is not None:
            ip, userService, iads, trans, itrans = res
            # This returns a response object in fact
            return itrans.getLink(userService, trans, ip, request.os, request.user, webPassword(request), request)
    except Exception, e:
        logger.exception("Exception")
        return errors.exceptionView(request, e)

    return render_to_response(theme.template('service_not_ready.html'), context_instance=RequestContext(request))


@webLoginRequired(admin=False)
def transcomp(request, idTransport, componentId):
    try:
        # We got translated first id
        trans = Transport.objects.get(uuid=idTransport.upper())
        itrans = trans.getInstance()
        res = itrans.getHtmlComponent(trans.uuid, OsDetector.getOsFromRequest(request), componentId)
        response = HttpResponse(res[1], content_type=res[0])
        response['Content-Length'] = len(res[1])
        return response
    except Exception, e:
        return errors.exceptionView(request, e)


def transportIcon(request, idTrans):
    try:
        icon = Transport.objects.get(uuid=idTrans).getInstance().icon(False)
        return HttpResponse(icon, content_type='image/png')
    except Exception:
        return HttpResponseRedirect('/static/img/unknown.png')


@cache_page(86400, key_prefix='img')
def serviceImage(request, idImage):
    try:
        icon = Image.objects.get(uuid=idImage)
        return icon.imageResponse()
    except Image.DoesNotExist:
        pass  # Tries to get image from transport

    try:
        icon = Transport.objects.get(uuid=idImage).getInstance().icon(False)
        return HttpResponse(icon, content_type='image/png')
    except Exception:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')


@webLoginRequired(admin=False)
@never_cache
def clientEnabler(request, idService, idTransport):

    # Maybe we could even protect this even more by limiting referer to own server /? (just a meditation..)

    url = ''
    error = _('Service not ready. Please, try again in a while.')
    try:
        res = getService(request, idService, idTransport, doTest=False)
        if res is not None:

            scrambler = cryptoManager().randomString(32)
            password = cryptoManager().xor(webPassword(request), scrambler)

            _x, userService, _x, trans, _x = res

            data = {
                'service': 'A' + userService.uuid,
                'transport': trans.uuid,
                'user': request.user.uuid,
                'password': password
            }

            ticket = TicketStore.create(data)
            error = ''
            url = html.udsLink(request, ticket, scrambler)
    except Exception as e:
        error = six.text_type(e)

    # Not ready, show message and return to this page in a while
    return HttpResponse('{{ "url": "{}", "error": "{}" }}'.format(url, error), content_type='application/json')
