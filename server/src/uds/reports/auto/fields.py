# -*- coding: utf-8 -*-

#
# Copyright (c) 2020-2021 Virtual Cable S.L.U.
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
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import types
from uds.core.util import dateutils
from uds.core.ui import gui

logger = logging.getLogger(__name__)


def start_date_field(order: int) -> gui.DateField:
    return gui.DateField(
        order=order,
        label=_('Starting date'),
        tooltip=_('Starting date for report'),
        default=dateutils.start_of_month,
        required=True,
    )


def single_date_field(order: int) -> gui.DateField:
    return gui.DateField(
        order=order,
        label=_('Date'),
        tooltip=_('Date for report'),
        default=dateutils.today,
        required=True,
    )


def end_date_field(order: int) -> gui.DateField:
    return gui.DateField(
        order=order,
        label=_('Ending date'),
        tooltip=_('ending date for report'),
        default=dateutils.tomorrow,
        required=True,
    )


def intervals_field(order: int) -> gui.ChoiceField:
    return gui.ChoiceField(
        label=_('Report data interval'),
        order=order,
        choices={
            'hour': _('Hourly'),
            'day': _('Daily'),
            'week': _('Weekly'),
            'month': _('Monthly'),
        },
        tooltip=_('Interval for report data'),
        required=True,
        default='day',
    )


def source_field(
    order: int, data_source: str, multiple: bool
) -> typing.Union[gui.ChoiceField, gui.MultiChoiceField, None]:
    if not data_source:
        return None

    data_source = data_source.split('.')[0]
    # logger.debug('SOURCE: %s', data_source)

    field_type: typing.Type[gui.ChoiceField|gui.MultiChoiceField] = gui.ChoiceField if not multiple else gui.MultiChoiceField

    labels: typing.Any = {
        'ServicePool': (_('Service pool'), _('Service pool for report')),
        'Authenticator': (_('Authenticator'), _('Authenticator for report')),
        'Service': (_('Service'), _('Service for report')),
        'Provider': (_('Service provider'), _('Service provider for report')),
    }.get(data_source)

    logger.debug('Labels: %s, %s', labels, field_type)

    return field_type(label=labels[0], order=order, tooltip=labels[1], required=True)


def source_field_data(
    model: typing.Any,
    field: typing.Union[gui.ChoiceField, gui.MultiChoiceField],
) -> None:
    data_list: list[types.ui.ChoiceItem] = [
        gui.choice_item(str(x.uuid), x.name) for x in model.objects.all().order_by('name')
    ]

    if isinstance(field, gui.MultiChoiceField):
        data_list.insert(0, {'id': '0-0-0-0', 'text': _('All')})

    field.set_choices(data_list)
