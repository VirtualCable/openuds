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

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

from uds.core.auths.auth import webLoginRequired, webPassword
from uds.models import DeployedService, Transport, UserService, Image
from uds.core.ui.images import DEFAULT_IMAGE
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core.util import log
from uds.core.util.stats import events
from uds.core.ui import theme

import uds.web.errors as errors


import logging

logger = logging.getLogger(__name__)


@webLoginRequired
def service(request, idService, idTransport):
    kind, idService = idService[0], idService[1:]
    try:
        logger.debug('Kind of service: {0}, idService: {1}'.format(kind, idService))
        if kind == 'A':  # This is an assigned service
            ads = UserService.objects.get(uuid=idService)
        else:
            ds = DeployedService.objects.get(uuid=idService)
            # We first do a sanity check for this, if the user has access to this service
            # If it fails, will raise an exception
            ds.validateUser(request.user)
            # Now we have to locate an instance of the service, so we can assign it to user.
            ads = UserServiceManager.manager().getAssignationForUser(ds, request.user)
        logger.debug('Found service: {0}'.format(ads))
        trans = Transport.objects.get(uuid=idTransport)
        # Test if the service is ready
        if ads.isReady():
            log.doLog(ads, log.INFO, "User {0} from {1} has initiated access".format(request.user.name, request.ip), log.WEB)
            # If ready, show transport for this service, if also ready ofc
            iads = ads.getInstance()
            ip = iads.getIp()
            events.addEvent(ads.deployed_service, events.ET_ACCESS, username=request.user.name, srcip=request.ip, dstip=ip, uniqueid=ads.unique_id)
            if ip is not None:
                itrans = trans.getInstance()
                if itrans.isAvailableFor(ip):
                    log.doLog(ads, log.INFO, "User service ready, rendering transport", log.WEB)
                    transportHtml = itrans.renderForHtml(ads, trans, ip, request.session['OS'], request.user, webPassword(request))
                    UserServiceManager.manager().notifyPreconnect(ads, itrans.processedUser(ads, request.user), itrans.protocol)
                    return render_to_response(theme.template('show_transport.html'), {'transport': transportHtml, 'nolang': True}, context_instance=RequestContext(request))
                else:
                    log.doLog(ads, log.WARN, "User service is not accessible (ip {0})".format(ip), log.TRANSPORT)
                    logger.debug('Transport is not ready for user service {0}'.format(ads))
            else:
                logger.debug('Ip not available from user service {0}'.format(ads))
        else:
            log.doLog(ads, log.WARN, "User {0} from {1} tried to access, but machine was not ready".format(request.user.name, request.ip), log.WEB)
        # Not ready, show message and return to this page in a while
        return render_to_response(theme.template('service_not_ready.html'), context_instance=RequestContext(request))
    except Exception, e:
        logger.exception("Exception")
        return errors.exceptionView(request, e)


@webLoginRequired
def transcomp(request, idTransport, componentId):
    try:
        # We got translated first id
        trans = Transport.objects.get(uuid=idTransport.upper())
        itrans = trans.getInstance()
        res = itrans.getHtmlComponent(trans.uuid, request.session['OS'], componentId)
        response = HttpResponse(res[1], content_type=res[0])
        response['Content-Length'] = len(res[1])
        return response
    except Exception, e:
        return errors.exceptionView(request, e)


@webLoginRequired
def sernotify(request, idUserService, notification):
    try:
        if notification == 'hostname':
            hostname = request.GET.get('hostname', None)
            ip = request.GET.get('ip', None)
            if ip is not None and hostname is not None:
                us = UserService.objects.get(uuid=idUserService)
                us.setConnectionSource(ip, hostname)
            else:
                return HttpResponse('Invalid request!', 'text/plain')
        elif notification == "log":
            message = request.GET.get('message', None)
            level = request.GET.get('level', None)
            if message is not None and level is not None:
                us = UserService.objects.get(uuid=idUserService)
                log.doLog(us, level, message, log.TRANSPORT)
            else:
                return HttpResponse('Invalid request!', 'text/plain')
    except Exception as e:
        logger.exception("Exception")
        return errors.errorView(request, e)
    return HttpResponse('ok', content_type='text/plain')


def transportIcon(request, idTrans):
    try:
        icon = Transport.objects.get(uuid=idTrans).getInstance().icon(False)
        return HttpResponse(icon, content_type='image/png')
    except Exception:
        return HttpResponseRedirect('/static/img/unknown.png')


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
