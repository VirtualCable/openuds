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
from django.http import HttpResponse, HttpResponseRedirect, HttpResponsePermanentRedirect
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.views.decorators.cache import never_cache
from django.shortcuts import render_to_response
from django.template import RequestContext

from uds.core.auths.auth import webLogin, webLogout, authenticateViaCallback, authLogLogin, getUDSCookie
from uds.models import Authenticator, DeployedService
from uds.core.managers import userServiceManager
from uds.core.managers import cryptoManager
from uds.core.util import html
from uds.core.util import OsDetector
from uds.core.util.State import State
from uds.core.ui import theme

from uds.models import TicketStore

from uds.core.auths.Exceptions import InvalidUserException
from uds.core.services.Exceptions import InvalidServiceException, ServiceNotReadyError

import uds.web.errors as errors

import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-07-18'


@csrf_exempt
def authCallback(request, authName):
    '''
    This url is provided so external SSO authenticators can get an url for
    redirecting back the users.

    This will invoke authCallback of the requested idAuth and, if this represents
    an authenticator that has an authCallback
    '''
    from uds.core import auths
    try:
        authenticator = Authenticator.objects.get(name=authName)
        params = request.GET.copy()
        params.update(request.POST)
        logger.debug('Request session:%s -> %s, %s', request.ip, request.session.keys(), request.session.session_key)

        params['_request'] = request
        # params['_session'] = request.session
        # params['_user'] = request.user

        logger.debug('Auth callback for {0} with params {1}'.format(authenticator, params.keys()))

        user = authenticateViaCallback(authenticator, params)

        os = OsDetector.getOsFromUA(request.META['HTTP_USER_AGENT'])

        if user is None:
            authLogLogin(request, authenticator, '{0}'.format(params), 'Invalid at auth callback')
            raise auths.Exceptions.InvalidUserException()

        response = HttpResponseRedirect(reverse('Index'))

        webLogin(request, response, user, '')  # Password is unavailable in this case
        request.session['OS'] = os
        # Now we render an intermediate page, so we get Java support from user
        # It will only detect java, and them redirect to Java

        return response
    except auths.Exceptions.Redirect as e:
        return HttpResponseRedirect(request.build_absolute_uri(str(e)))
    except auths.Exceptions.Logout as e:
        return webLogout(request, request.build_absolute_uri(str(e)))
    except Exception as e:
        logger.exception('authCallback')
        return errors.exceptionView(request, e)

    # Will never reach this
    raise RuntimeError('Unreachable point reached!!!')


@csrf_exempt
def authInfo(request, authName):
    '''
    This url is provided so authenticators can provide info (such as SAML metadata)

    This will invoke getInfo on requested authName. The search of the authenticator is done
    by name, so it's easier to access from external sources
    '''
    from uds.core import auths
    try:
        authenticator = Authenticator.objects.get(name=authName)
        authInstance = authenticator.getInstance()
        if authInstance.getInfo == auths.Authenticator.getInfo:
            raise Exception()  # This authenticator do not provides info

        params = request.GET.copy()
        params['_request'] = request

        info = authInstance.getInfo(params)

        if info is None:
            raise Exception()  # This auth do not provides info

        if type(info) is list or type(info) is tuple:
            return HttpResponse(info[0], content_type=info[1])

        return HttpResponse(info)
    except Exception:
        return HttpResponse(_('Authenticator does not provide information'))


@never_cache
def ticketAuth(request, ticketId):
    '''
    Used to authenticate an user via a ticket
    '''
    try:
        data = TicketStore.get(ticketId, invalidate=True)

        try:
            # Extract ticket.data from ticket.data storage, and remove it if success
            username = data['username']
            groups = data['groups']
            auth = data['auth']
            realname = data['realname']
            servicePool = data['servicePool']
            password = cryptoManager().decrypt(data['password'])
            transport = data['transport']
        except Exception:
            logger.error('Ticket stored is not valid')
            raise InvalidUserException()

        auth = Authenticator.objects.get(uuid=auth)
        # If user does not exists in DB, create it right now
        # Add user to groups, if they exists...
        grps = []
        for g in groups:
            try:
                grps.append(auth.groups.get(uuid=g))
            except Exception:
                logger.debug('Group list has changed since ticket assignment')

        if len(grps) == 0:
            logger.error('Ticket has no valid groups')
            raise Exception('Invalid ticket authentication')

        usr = auth.getOrCreateUser(username, realname)
        if usr is None or State.isActive(usr.state) is False:  # If user is inactive, raise an exception
            raise InvalidUserException()

        # Add groups to user (replace existing groups)
        usr.groups = grps

        # Force cookie generation
        webLogin(request, None, usr, password)

        request.user = usr  # Temporarily store this user as "authenticated" user, next requests will be done using session
        request.session['ticket'] = '1'  # Store that user access is done using ticket

        logger.debug("Service & transport: {}, {}".format(servicePool, transport))
        # for v in DeployedService.objects.all():
        #    logger.debug("{} {}".format(v.uuid, v.name))

        # Check if servicePool is part of the ticket
        if servicePool is not None:
            # If service pool is in there, also is transport
            # Deferred update transport
            servicePoolDb = DeployedService.objects.get(uuid=servicePool)
            for t in servicePoolDb.transports.order_by('priority'):
                typeTrans = t.getType()
                if t.validForIp(request.ip) and typeTrans.supportsOs(request.os['OS']) and t.validForOs(request.os['OS']):
                    transport = t.uuid
                    break

            res = userServiceManager().getService(request.user, request.ip, 'F' + servicePool, transport, False)
            _x, userService, _x, transport, _x = res

            transportInstance = transport.getInstance()
            if transportInstance.ownLink is True:
                link = reverse('TransportOwnLink', args=('A' + userService.uuid, transport.uuid))
            else:
                link = html.udsAccessLink(request, 'A' + userService.uuid, transport.uuid)

            response = render_to_response(
                theme.template('simpleLauncher.html'),
                {
                    'link': link
                },
                context_instance=RequestContext(request)
            )
        else:
            response = HttpResponsePermanentRedirect(reverse('uds.web.views.index'))

        # Now ensure uds cookie is at response
        getUDSCookie(request, response, True)
        return response
    except ServiceNotReadyError as e:
        return render_to_response(
            theme.template('service_not_ready.html'),
            {
                'fromLauncher': True,
                'code': e.code
            },
            context_instance=RequestContext(request)
        )

    except TicketStore.InvalidTicket:
        return render_to_response(
            theme.template('simpleLauncherAlreadyLaunched.html'),
            context_instance=RequestContext(request)
        )
    except Authenticator.DoesNotExist:
        logger.error('Ticket has an non existing authenticator')
        return errors.exceptionView(request, InvalidUserException())
    except DeployedService.DoesNotExist:
        logger.error('Ticket has an invalid Service Pool')
        return errors.exceptionView(request, InvalidServiceException())
    except Exception as e:
        logger.exception('Exception')
        return errors.exceptionView(request, e)
