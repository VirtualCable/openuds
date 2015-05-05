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

from django.shortcuts import render_to_response
from django.shortcuts import render
from django.core.urlresolvers import reverse
from django.template import RequestContext

from uds.core.auths.auth import webLoginRequired

from uds.models import DeployedService, Transport, UserService, Network
from uds.core.util.Config import GlobalConfig
from uds.core.util import html

from uds.core.ui import theme
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core import VERSION

import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-05-05'


def about(request):
    '''
    Shows the about page
    :param request: http request
    '''
    return render_to_response(
        theme.template('about.html'),
        {
            'version': VERSION,
        },
        context_instance=RequestContext(request)
    )


@webLoginRequired(admin=False)
def index(request):
    '''
    Renders the main page.
    :param request: http request
    '''
    # Session data
    os = request.os

    # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
    groups = list(request.user.getGroups())
    availServices = DeployedService.getDeployedServicesForGroups(groups)
    availUserServices = UserService.getUserAssignedServices(request.user)

    # Information for administrators
    nets = ''
    validTrans = ''

    logger.debug('OS: {0}'.format(os['OS']))

    if request.user.isStaff():
        nets = ','.join([n.name for n in Network.networksFor(request.ip)])
        tt = []
        for t in Transport.objects.all():
            if t.validForIp(request.ip):
                tt.append(t.name)
        validTrans = ','.join(tt)

    # Extract required data to show to user
    services = []
    # Select assigned user services
    for svr in availUserServices:
        trans = []
        for t in svr.transports.all().order_by('priority'):
            typeTrans = t.getType()
            if t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']):
                if typeTrans.ownLink is True:
                    link = reverse('TransportOwnLink', args=('A' + svr.uuid, t.uuid))
                else:
                    link = html.udsAccessLink(request, 'A' + svr.uuid, t.uuid)
                trans.append(
                    {
                        'id': t.uuid,
                        'name': t.name,
                        'link': link
                    }
                )
        if svr.deployed_service.image is not None:
            imageId = svr.deployed_service.image.uuid
        else:
            imageId = 'x'  # Invalid

        services.append({
            'id': 'A' + svr.uuid,
            'name': svr['name'],
            'transports': trans,
            'imageId': imageId,
            'show_transports': svr.deployed_service.show_transports,
            'maintenance': svr.deployed_service.service.provider.maintenance_mode,
            'in_use': svr.in_use,
        })

    logger.debug(services)

    # Now generic user service
    for svr in availServices:
        # Generate ticket

        trans = []
        for t in svr.transports.all().order_by('priority'):
            typeTrans = t.getType()
            if t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']):
                if typeTrans.ownLink is True:
                    link = reverse('TransportOwnLink', args=('F' + svr.uuid, t.uuid))
                else:
                    link = html.udsAccessLink(request, 'F' + svr.uuid, t.uuid)
                trans.append(
                    {
                        'id': t.uuid,
                        'name': t.name,
                        'link': link
                    }
                )
        if svr.image is not None:
            imageId = svr.image.uuid
        else:
            imageId = 'x'

        # Locate if user service has any already assigned user service for this
        ads = UserServiceManager.manager().getExistingAssignationForUser(svr, request.user)
        if ads is None:
            in_use = False
        else:
            in_use = ads.in_use

        services.append({
            'id': 'F' + svr.uuid,
            'name': svr.name,
            'transports': trans,
            'imageId': imageId,
            'show_transports': svr.show_transports,
            'maintenance': svr.service.provider.maintenance_mode,
            'in_use': in_use,
        })

    logger.debug('Services: {0}'.format(services))

    services = sorted(services, key=lambda s: s['name'].upper())

    autorun = False
    if len(services) == 1 and GlobalConfig.AUTORUN_SERVICE.getBool(True) and len(services[0]['transports']) > 0:
        if request.session.get('autorunDone', '0') == '0':
            request.session['autorunDone'] = '1'
            autorun = True
            # return redirect('uds.web.views.service', idService=services[0]['id'], idTransport=services[0]['transports'][0]['id'])

    response = render_to_response(
        theme.template('index.html'),
        {
            'services': services,
            'ip': request.ip,
            'nets': nets,
            'transports': validTrans,
            'autorun': autorun
        },
        context_instance=RequestContext(request)
    )
    return response
