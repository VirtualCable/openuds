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
from django.shortcuts import redirect
from django.template import RequestContext

from uds.core.auths.auth import webLoginRequired

from uds.models import DeployedService, Transport, UserService, Network
from uds.core.util.Config import GlobalConfig
from uds.core.ui import theme


import logging

logger = logging.getLogger(__name__)


def about(request):
    '''
    Shows the about page
    :param request: http request
    '''
    return render(request, theme.template('about.html'))


@webLoginRequired
def index(request):
    '''
    Renders the main page.
    :param request: http request
    '''
    # Session data
    os = request.session['OS']
    java = request.session.get('java', None)

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
        # Skip maintenance services...
        if svr.deployed_service.service.provider.maintenance_mode is True:
            continue
        trans = []
        for t in svr.transports.all().order_by('priority'):
            typeTrans = t.getType()
            if t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']):
                trans.append({'id': t.uuid, 'name': t.name, 'needsJava': t.getType().needsJava})
        if svr.deployed_service.image is not None:
            imageId = svr.deployed_service.image.uuid
        else:
            imageId = 'x'  # Invalid
        services.append({'id': 'A' + svr.uuid, 'name': svr['name'], 'transports': trans, 'imageId': imageId, 'show_transports': svr.deployed_service.show_transports})

    # Now generic user service
    for svr in availServices:
        if svr.service.provider.maintenance_mode is True:
            continue
        trans = []
        for t in svr.transports.all().order_by('priority'):
            if t.validForIp(request.ip):
                typeTrans = t.getType()
                if typeTrans.supportsOs(os['OS']):
                    trans.append({'id': t.uuid, 'name': t.name, 'needsJava': typeTrans.needsJava})
        if svr.image is not None:
            imageId = svr.image.uuid
        else:
            imageId = 'x'
        services.append({'id': 'F' + svr.uuid, 'name': svr.name, 'transports': trans, 'imageId': imageId, 'show_transports': svr.show_transports})

    logger.debug('Services: {0}'.format(services))

    services = sorted(services, key=lambda s: s['name'].upper())

    if len(services) == 1 and GlobalConfig.AUTORUN_SERVICE.get(True) == '1' and len(services[0]['transports']) > 0:
        if request.session.get('autorunDone', '0') == '0':
            request.session['autorunDone'] = '1'
            return redirect('uds.web.views.service', idService=services[0]['id'], idTransport=services[0]['transports'][0]['id'])

    response = render_to_response(theme.template('index.html'),
                                  {'services': services, 'java': java, 'ip': request.ip, 'nets': nets, 'transports': validTrans},
                                  context_instance=RequestContext(request)
                                  )
    return response
