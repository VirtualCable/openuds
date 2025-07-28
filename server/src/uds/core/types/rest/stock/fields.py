# -*- coding: utf-8 -*-
#
# Copyright (c) 2025 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import enum

from django.utils.translation import gettext_lazy as _

# Avoid circular import by importing ui here insetad of at the top
from ... import ui


class StockField(enum.StrEnum):
    """
    This class contains the static fields that are common to all models.
    It is used to define the fields that are common to all models in the system.
    """

    TAGS = 'tags'
    NAME = 'name'
    COMMENTS = 'comments'
    PRIORITY = 'priority'
    LABEL = 'small_name'
    NETWORKS = 'networks'

    def get_fields(self) -> list['ui.GuiElement']:
        """
        Returns the GUI elements for the field.
        """
        from uds.models import Network  # Import here to avoid circular import

        # Get a copy to ensure we do not modify the original
        field_gui = [i.copy() for i in _STATIC_FLDS[self]]

        # Special cases, as network choices are dynamic
        if self.value == self.NETWORKS:
            field_gui[0]['gui']['choices'] = sorted(
                [{'id': x.uuid, 'text': x.name} for x in Network.objects.all()],
                key=lambda x: x['text'].lower(),
            )

        return field_gui


_STATIC_FLDS: typing.Final[dict[StockField, list['ui.GuiElement']]] = {
    StockField.TAGS: [
        {
            'name': 'tags',
            'gui': {
                'label': _('Tags'),
                'type': ui.FieldType.TAGLIST,
                'tooltip': _('Tags for this element'),
                'order': 0 - 110,
            },
        }
    ],
    StockField.NAME: [
        {
            'name': 'name',
            'gui': {
                'type': ui.FieldType.TEXT,
                'required': True,
                'label': _('Name'),
                'length': 128,
                'tooltip': _('Name of this element'),
                'order': 0 - 100,
            },
        }
    ],
    StockField.COMMENTS: [
        {
            'name': 'comments',
            'gui': {
                'label': _('Comments'),
                'type': ui.FieldType.TEXT,
                'lines': 3,
                'tooltip': _('Comments for this element'),
                'length': 256,
                'order': 0 - 90,
            },
        }
    ],
    StockField.PRIORITY: [
        {
            'name': 'priority',
            'gui': {
                'label': _('Priority'),
                'type': ui.FieldType.NUMERIC,
                'required': True,
                'default': 1,
                'length': 4,
                'tooltip': _('Selects the priority of this element (lower number means higher priority)'),
                'order': 0 - 80,
            },
        }
    ],
    StockField.LABEL: [
        {
            'name': 'small_name',
            'gui': {
                'label': _('Label'),
                'type': ui.FieldType.TEXT,
                'required': True,
                'length': 128,
                'tooltip': _('Label for this element'),
                'order': 0 - 70,
            },
        }
    ],
    StockField.NETWORKS: [
        {
            'name': 'networks',
            'gui': {
                'label': _('Networks'),
                'type': ui.FieldType.MULTICHOICE,
                'tooltip': _('Networks associated. If No network selected, will mean "all networks"'),
                'choices': [],  # Will be filled dynamically
                'order': 101,
                'tab': ui.Tab.ADVANCED,
            },
        },
        {
            'name': 'net_filtering',
            'gui': {
                'label': _('Network Filtering'),
                'type': ui.FieldType.CHOICE,  # Type of network filtering
                'default': 'n',
                'choices': [
                    {'id': 'n', 'text': _('No filtering')},
                    {'id': 'a', 'text': _('Allow selected networks')},
                    {'id': 'd', 'text': _('Deny selected networks')},
                ],
                'tooltip': _(
                    'Type of network filtering. Use "Disabled" to disable origin check, "Allow" to only enable for selected networks or "Deny" to deny from selected networks'
                ),
                'order': 100,  # At end
                'tab': ui.Tab.ADVANCED,
            },
        },
    ],
}
