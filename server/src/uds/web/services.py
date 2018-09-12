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
"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.urls import reverse
from django.utils.translation import ugettext
from django.utils import formats

from uds.models import DeployedService, Transport, UserService, Network, ServicesPoolGroup
from uds.core.util.Config import GlobalConfig
from uds.core.util import html

from uds.core.managers.UserServiceManager import UserServiceManager

import logging

logger = logging.getLogger(__name__)


def getServicesData(request):
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
    # Select assigned user services (manually assigned)
    for svr in availUserServices:
        trans = []
        for t in svr.transports.all().order_by('priority'):
            typeTrans = t.getType()
            if t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']) and t.validForOs(os['OS']):
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

        # If empty transports, do not include it on list
        if not trans:
            continue

        servicePool = svr.deployed_service

        if servicePool.image is not None:
            imageId = servicePool.image.uuid
        else:
            imageId = 'x'  # Invalid

        # Extract app group
        group = servicePool.servicesPoolGroup if servicePool.servicesPoolGroup is not None else ServicesPoolGroup.default().as_dict

        services.append({
            'id': 'A' + svr.uuid,
            'name': servicePool.name,
            'visual_name': servicePool.visual_name,
            'description': servicePool.comments,
            'group': group,
            'transports': trans,
            'imageId': imageId,
            'show_transports': servicePool.show_transports,
            'allow_users_remove': servicePool.allow_users_remove,
            'allow_users_reset': servicePool.allow_users_reset,
            'maintenance': servicePool.isInMaintenance(),
            'not_accesible': not servicePool.isAccessAllowed(),
            'in_use': svr.in_use,
            'to_be_replaced': False,  # Manually assigned will not be autoremoved never
            'comments': servicePool.comments,
        })

    logger.debug(services)

    # Now generic user service
    for svr in availServices:
        trans = []
        for t in svr.transports.all().order_by('priority'):
            typeTrans = t.getType()
            if typeTrans is None:  # This may happen if we "remove" a transport type but we have a transport of that kind on DB
                continue
            if t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']) and t.validForOs(os['OS']):
                if typeTrans.ownLink is True:
                    link = reverse('TransportOwnLink', args=('F' + svr.uuid, t.uuid))
                else:
                    link = html.udsAccessLink(request, 'F' + svr.uuid, t.uuid)
                trans.append(
                    {
                        'id': t.uuid,
                        'name': t.name,
                        'link': link,
                        'priority': t.priority
                    }
                )

        # If empty transports, do not include it on list
        if not trans:
            continue

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

        group = svr.servicesPoolGroup.as_dict if svr.servicesPoolGroup is not None else ServicesPoolGroup.default().as_dict

        tbr = svr.toBeReplaced()
        if tbr is not None:
            tbr = formats.date_format(tbr, "SHORT_DATETIME_FORMAT")
            tbrt = ugettext('This service is about to be replaced by a new version. Please, close the session before {} and save all your work to avoid loosing it.').format(tbr)
        else:
            tbrt = ''

        services.append({
            'id': 'F' + svr.uuid,
            'name': svr.name,
            'visual_name': svr.visual_name,
            'description': svr.comments,
            'group': group,
            'transports': trans,
            'imageId': imageId,
            'show_transports': svr.show_transports,
            'allow_users_remove': svr.allow_users_remove,
            'allow_users_reset': svr.allow_users_reset,
            'maintenance': svr.isInMaintenance(),
            'not_accesible': not svr.isAccessAllowed(),
            'in_use': in_use,
            'to_be_replaced': tbr,
            'to_be_replaced_text': tbrt,
            'comments': svr.comments,
        })

    logger.debug('Services: {0}'.format(services))

    services = sorted(services, key=lambda s: s['name'].upper())

    autorun = False
    if len(services) == 1 and GlobalConfig.AUTORUN_SERVICE.getBool(True) and len(services[0]['transports']) > 0:
        if request.session.get('autorunDone', '0') == '0':
            request.session['autorunDone'] = '1'
            autorun = True
            # return redirect('uds.web.views.service', idService=services[0]['id'], idTransport=services[0]['transports'][0]['id'])

    return {
            'services': services,
            'ip': request.ip,
            'nets': nets,
            'transports': validTrans,
            'autorun': autorun
    }
