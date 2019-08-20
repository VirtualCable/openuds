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
import logging
import typing

from django.utils.translation import ugettext
from django.utils import formats
from django.urls.base import reverse

from uds.models import ServicePool, Transport, Network, ServicePoolGroup, MetaPool
from uds.core.util.config import GlobalConfig
from uds.core.util import html

from uds.core.managers import userServiceManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import HttpRequest # pylint: disable=ungrouped-imports


logger = logging.getLogger(__name__)


def getServicesData(request: 'HttpRequest') -> typing.Dict[str, typing.Any]:  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """Obtains the service data dictionary will all available services for this request

    Arguments:
        request {HttpRequest} -- request from where to xtract credentials

    Returns:
        typing.Dict[str, typing.Any] --  Keys has this:
            'services': services,
            'ip': request.ip,
            'nets': nets,
            'transports': validTrans,
            'autorun': autorun

    """
    # Session data
    os: typing.Dict[str, str] = request.os

    # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
    groups = list(request.user.getGroups())
    availServicePools = ServicePool.getDeployedServicesForGroups(groups)
    availMetaPools = MetaPool.getForGroups(groups)

    # Information for administrators
    nets = ''
    validTrans = ''

    logger.debug('OS: %s', os['OS'])

    if request.user.isStaff():
        nets = ','.join([n.name for n in Network.networksFor(request.ip)])
        tt = []
        for t in Transport.objects.all():
            if t.validForIp(request.ip):
                tt.append(t.name)
        validTrans = ','.join(tt)

    logger.debug('Checking meta pools: %s', availMetaPools)
    services = []
    # Add meta pools data first
    for meta in availMetaPools:
        # Check that we have access to at least one transport on some of its children
        hasUsablePools = False
        in_use = False
        for pool in meta.pools.all():
            # if pool.isInMaintenance():
            #    continue
            for t in pool.transports.all():
                typeTrans = t.getType()
                if t.getType() and t.validForIp(request.ip) and typeTrans.supportsOs(os['OS']) and t.validForOs(os['OS']):
                    hasUsablePools = True
                    break

            if not in_use:
                assignedUserService = userServiceManager().getExistingAssignationForUser(pool, request.user)
                if assignedUserService:
                    in_use = assignedUserService.in_use

            # Stop when 1 usable pool is found
            if hasUsablePools:
                break

        # If no usable pools, this is not visible
        if hasUsablePools:
            group = meta.servicesPoolGroup.as_dict if meta.servicesPoolGroup else ServicePoolGroup.default().as_dict

            services.append({
                'id': 'M' + meta.uuid,
                'name': meta.name,
                'visual_name': meta.visual_name,
                'description': meta.comments,
                'group': group,
                'transports': [{
                    'id': 'meta',
                    'name': 'meta',
                    'link': html.udsMetaLink(request, 'M' + meta.uuid),
                    'priority': 0
                }],
                'imageId': meta.image and meta.image.uuid or 'x',
                'show_transports': False,
                'allow_users_remove': False,
                'allow_users_reset': False,
                'maintenance': meta.isInMaintenance(),
                'not_accesible': not meta.isAccessAllowed(),
                'in_use': in_use,
                'to_be_replaced': None,
                'to_be_replaced_text': '',
            })

    # Now generic user service
    for svr in availServicePools:
        # Skip pools that are part of meta pools
        if svr.is_meta:
            continue

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
        ads = userServiceManager().getExistingAssignationForUser(svr, request.user)
        if ads is None:
            in_use = False
        else:
            in_use = ads.in_use

        group = svr.servicesPoolGroup.as_dict if svr.servicesPoolGroup else ServicePoolGroup.default().as_dict

        tbr = svr.toBeReplaced(request.user)
        if tbr:
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
        })

    logger.debug('Services: {0}'.format(services))

    # Sort services and remove services with no transports...
    services = [s for s in sorted(services, key=lambda s: s['name'].upper()) if s['transports']]

    autorun = False
    if len(services) == 1 and GlobalConfig.AUTORUN_SERVICE.getBool(True) and services[0]['transports']:
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
