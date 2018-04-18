# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

from django.utils.translation import ugettext as _
import logging
from uds.core.ui import gui

logger = logging.getLogger(__name__)


def getResources(parameters):
    """
    This helper is designed as a callback for Project Selector
    """
    from .Provider import Provider
    from uds.core.Environment import Environment
    logger.debug('Parameters received by getResources Helper: {0}'.format(parameters))
    env = Environment(parameters['ev'])
    provider = Provider(env)
    provider.unserialize(parameters['ov'])

    api = provider.api(parameters['project'], parameters['region'])

    zones = [gui.choiceItem(z, z) for z in api.listAvailabilityZones()]
    networks = [gui.choiceItem(z['id'], z['name']) for z in api.listNetworks()]
    flavors = [gui.choiceItem(z['id'], z['name']) for z in api.listFlavors()]
    securityGroups = [gui.choiceItem(z['id'], z['name']) for z in api.listSecurityGroups()]
    volumeTypes = [gui.choiceItem('-', _('None'))] + [gui.choiceItem(t['id'], t['name']) for t in api.listVolumeTypes()]

    data = [
        {'name': 'availabilityZone', 'values': zones},
        {'name': 'network', 'values': networks},
        {'name': 'flavor', 'values': flavors},
        {'name': 'securityGroups', 'values': securityGroups},
        {'name': 'volumeType', 'values': volumeTypes},
    ]
    logger.debug('Return data: {}'.format(data))
    return data


def getVolumes(parameters):
    """
    This helper is designed as a callback for Zone Selector
    """
    from .Provider import Provider
    from uds.core.Environment import Environment
    logger.debug('Parameters received by getVolumes Helper: {0}'.format(parameters))
    env = Environment(parameters['ev'])
    provider = Provider(env)
    provider.unserialize(parameters['ov'])

    api = provider.api(parameters['project'], parameters['region'])

    volumes = [gui.choiceItem(v['id'], v['name']) for v in api.listVolumes() if
               v['name'] != '' and v['availability_zone'] == parameters['availabilityZone']]

    data = [
        {'name': 'volume', 'values': volumes},
    ]
    logger.debug('Return data: {}'.format(data))
    return data
