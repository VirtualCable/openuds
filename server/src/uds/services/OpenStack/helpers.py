# -*- coding: utf-8 -*-

#
# Copyright (c) 2016-2019 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
import collections.abc

from django.utils.translation import gettext as _
from uds.core import types
from uds.core.ui import gui

from . import openstack

logger = logging.getLogger(__name__)


def getApi(parameters: dict[str, str]) -> tuple[openstack.Client, bool]:
    from .provider_legacy import ProviderLegacy
    from .provider import OpenStackProvider
    from uds.core.environment import Environment

    env = Environment(parameters['ev'])
    provider: typing.Union[ProviderLegacy, OpenStackProvider]
    if parameters['legacy'] == 'true':
        provider = ProviderLegacy(env)
    else:
        provider = OpenStackProvider(env)

    provider.deserialize(parameters['ov'])

    if isinstance(provider, OpenStackProvider):
        useSubnetsName = provider.use_subnets_name.as_bool()
    else:
        useSubnetsName = False

    return (provider.api(parameters['project'], parameters['region']), useSubnetsName)


def get_resources(
    parameters: dict[str, str]
) -> types.ui.CallbackResultType:
    '''
    This helper is designed as a callback for Project Selector
    '''
    api, nameFromSubnets = getApi(parameters)

    zones = [gui.choice_item(z, z) for z in api.listAvailabilityZones()]
    networks = [
        gui.choice_item(z['id'], z['name'])
        for z in api.listNetworks(nameFromSubnets=nameFromSubnets)
    ]
    flavors = [gui.choice_item(z['id'], z['name']) for z in api.listFlavors()]
    securityGroups = [
        gui.choice_item(z['id'], z['name']) for z in api.listSecurityGroups()
    ]
    volumeTypes = [gui.choice_item('-', _('None'))] + [
        gui.choice_item(t['id'], t['name']) for t in api.listVolumeTypes()
    ]

    data: types.ui.CallbackResultType = [
        {'name': 'availabilityZone', 'choices': zones},
        {'name': 'network', 'choices': networks},
        {'name': 'flavor', 'choices': flavors},
        {'name': 'securityGroups', 'choices': securityGroups},
        {'name': 'volumeType', 'choices': volumeTypes},
    ]
    logger.debug('Return data: %s', data)
    return data


def get_volumes(
    parameters: dict[str, str]
) -> types.ui.CallbackResultType:
    '''
    This helper is designed as a callback for Zone Selector
    '''
    api, _ = getApi(parameters)
    # Source volumes are all available for us
    # volumes = [gui.choice_item(v['id'], v['name']) for v in api.listVolumes() if v['name'] != '' and v['availability_zone'] == parameters['availabilityZone']]
    volumes = [
        gui.choice_item(v['id'], v['name']) for v in api.listVolumes() if v['name'] != ''
    ]

    data: types.ui.CallbackResultType = [
        {'name': 'volume', 'choices': volumes},
    ]
    logger.debug('Return data: %s', data)
    return data
