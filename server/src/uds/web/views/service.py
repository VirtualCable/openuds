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
from uds.core.managers import userServiceManager, cryptoManager
from uds.models import TicketStore
from uds.core.ui.images import DEFAULT_IMAGE
from uds.core.ui import theme
from uds.core.util import OsDetector
from uds.models import Transport, Image
from uds.core.util import html
from uds.core.services.Exceptions import ServiceNotReadyError, MaxServicesReachedError

import uds.web.errors as errors

import six
import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-05-13'


@webLoginRequired(admin=False)
def transportOwnLink(request, idService, idTransport):
    try:
        res = userServiceManager().getService(request.user, request.ip, idService, idTransport)
        ip, userService, iads, trans, itrans = res  # @UnusedVariable
        # This returns a response object in fact
        return itrans.getLink(userService, trans, ip, request.os, request.user, webPassword(request), request)
    except ServiceNotReadyError as e:
        return render_to_response(
            theme.template('service_not_ready.html'),
            {
                'fromLauncher': False,
                'code': e.code
            },
            context_instance=RequestContext(request)
        )
    except Exception as e:
        logger.exception("Exception")
        return errors.exceptionView(request, e)

    # Will never reach this
    raise RuntimeError('Unreachable point reached!!!')


@cache_page(3600, key_prefix='img')
def transportIcon(request, idTrans):
    try:
        icon = Transport.objects.get(uuid=idTrans).getInstance().icon(False)
        return HttpResponse(icon, content_type='image/png')
    except Exception:
        return HttpResponseRedirect('/static/img/unknown.png')


@cache_page(3600, key_prefix='img')
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
    logger.debug('idService: {}, idTransport: {}'.format(idService, idTransport))
    url = ''
    error = _('Service not ready. Please, try again in a while.')
    try:
        res = userServiceManager().getService(request.user, request.ip, idService, idTransport, doTest=False)
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
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        error += ' (code {0:04X})'.format(e.code)
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "{}"'.format(idService))
        error = _('Maximum number of services reached. Contact your administrator')
    except Exception as e:
        logger.exception('Error')
        error = six.text_type(e)

    return HttpResponse(
        '{{ "url": "{}", "error": "{}" }}'.format(url, error),
        content_type='application/json'
    )
