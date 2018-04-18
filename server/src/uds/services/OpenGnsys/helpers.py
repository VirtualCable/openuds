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
    from .Provider import OGProvider
    from uds.core.Environment import Environment
    logger.debug('Parameters received by getResources Helper: {0}'.format(parameters))
    env = Environment(parameters['ev'])
    provider = OGProvider(env)
    provider.unserialize(parameters['ov'])

    api = provider.api

    labs = [gui.choiceItem('0', _('All Labs'))] + [gui.choiceItem(l['id'], l['name']) for l in api.getLabs(ou=parameters['ou'])]
    images = [gui.choiceItem(z['id'], z['name']) for z in api.getImages(ou=parameters['ou'])]

    data = [
        {'name': 'lab', 'values': labs},
        {'name': 'image', 'values': images},
    ]
    logger.debug('Return data: {}'.format(data))
    return data
