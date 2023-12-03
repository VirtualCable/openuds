# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import mfas, types
from uds.core.environment import Environment
from uds.core.util import ensure, permissions
from uds.REST.model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class MFA(ModelHandler):
    model = models.MFA
    save_fields = ['name', 'comments', 'tags', 'remember_device', 'validity']

    table_title = typing.cast(str, _('Multi Factor Authentication'))
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'comments': {'title': _('Comments')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self) -> typing.Iterable[type[mfas.MFA]]:
        return mfas.factory().providers().values()

    def getGui(self, type_: str) -> list[typing.Any]:
        mfaType = mfas.factory().lookup(type_)

        if not mfaType:
            raise self.invalidItemException()

        # Create a temporal instance to get the gui
        mfa = mfaType(Environment.getTempEnv(), None)

        localGui = self.addDefaultFields(mfa.guiDescription(), ['name', 'comments', 'tags'])
        self.addField(
            localGui,
            {
                'name': 'remember_device',
                'value': '0',
                'minValue': '0',
                'label': gettext('Device Caching'),
                'tooltip': gettext('Time in hours to cache device so MFA is not required again. User based.'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 111,
            },
        )
        self.addField(
            localGui,
            {
                'name': 'validity',
                'value': '5',
                'minValue': '0',
                'label': gettext('MFA code validity'),
                'tooltip': gettext('Time in minutes to allow MFA code to be used.'),
                'type': types.ui.FieldType.NUMERIC,
                'order': 112,
            },
        )

        return localGui

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        item = ensure.is_instance(item, models.MFA)
        type_ = item.getType()
        return {
            'id': item.uuid,
            'name': item.name,
            'remember_device': item.remember_device,
            'validity': item.validity,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'type': type_.getType(),
            'type_name': type_.name(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }
