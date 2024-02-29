# -*- coding: utf-8 -*-
#
# Copyright (c) 2015-2021 Virtual Cable S.L.U.
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
"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext as _

from uds.core import types
from uds.core.ui import gui
from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OGProvider

logger = logging.getLogger(__name__)


def get_resources(parameters: typing.Any) -> types.ui.CallbackResultType:
    logger.debug('Parameters received by getResources Helper: %s', parameters)
    provider = typing.cast(
        'OGProvider', models.Provider.objects.get(id=parameters['parent_uuid']).get_instance()
    )

    api = provider.api

    labs = [gui.choice_item('0', _('All Labs'))] + [
        gui.choice_item(l['id'], l['name']) for l in api.list_labs(ou=parameters['ou'])
    ]
    images = [gui.choice_item(z['id'], z['name']) for z in api.list_images(ou=parameters['ou'])]

    data: types.ui.CallbackResultType = [
        {'name': 'lab', 'choices': labs},
        {'name': 'image', 'choices': images},
    ]
    logger.debug('Return data from helper: %s', data)

    return data
