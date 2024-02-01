# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2019 Virtual Cable S.L.
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
import abc
import datetime
import logging
import typing
import collections.abc

from django.utils.translation import gettext, gettext_noop as _

from uds.core.ui import gui
from uds.core.reports import Report
from uds import models
from uds.core.ui.user_interface import UserInterfaceType

from . import fields

logger = logging.getLogger(__name__)

ReportAutoModel = typing.Union[
    models.Authenticator,
    models.ServicePool,
    models.Service,
    models.Provider,
]

reportAutoModelDct: collections.abc.Mapping[str, type[ReportAutoModel]] = {  # type: ignore
    'ServicePool': models.ServicePool,
    'Authenticator': models.Authenticator,
    'Service': models.Service,
    'Provider': models.Provider,
}


class ReportAutoType(UserInterfaceType):
    def __new__(mcs, name, bases, attrs) -> 'ReportAutoType':
        # Add gui for elements...
        order = 1

        # Check what source
        if attrs.get('data_source'):
            attrs['source'] = fields.source_field(order, attrs['data_source'], attrs['multiple'])
            order += 1

            # Check if date must be added
            if attrs.get('dates') == 'single':
                attrs['date_start'] = fields.single_date_field(order)
                order += 1
            elif attrs.get('dates') == 'range':
                attrs['date_start'] = fields.start_date_field(order)
                order += 1
                attrs['date_end'] = fields.end_date_field(order)
                order += 1

            # Check if data interval should be included
            if attrs.get('intervals'):
                attrs['interval'] = fields.intervals_field(order)
                order += 1

        return typing.cast('ReportAutoType', super().__new__(mcs, name, bases, attrs))
    
# pylint: disable=abstract-method
class ReportAuto(Report, metaclass=ReportAutoType):
    # Variables that will be overwriten on new class creation
    source: typing.ClassVar[typing.Union[gui.MultiChoiceField, gui.ChoiceField]]
    date_start: typing.ClassVar[gui.DateField]
    date_end: typing.ClassVar[gui.DateField]
    interval: typing.ClassVar[gui.ChoiceField]

    # Dates can be None, 'single' or 'range' to auto add date fields
    dates: typing.ClassVar[typing.Optional[str]] = None
    intervals: bool = False
    # Valid data_source:
    # * ServicePool.usage
    # * ServicePool.assigned
    # * Authenticator.users
    # * Authenticator.services
    # * Authenticator.user_with_services
    data_source: str = ''

    # If True, will allow selection of multiple "source" elements
    multiple: bool = False

    def getModel(self) -> type[ReportAutoModel]:
        data_source = self.data_source.split('.', maxsplit=1)[0]

        return reportAutoModelDct[data_source]

    def init_gui(self):
        # Fills datasource
        fields.source_field_data(self.getModel(), self.source)
        logger.debug('Source field data: %s', self.source)

    def get_model_records(self) -> collections.abc.Iterable[ReportAutoModel]:
        model = self.getModel()

        filters = [self.source.value] if isinstance(self.source, gui.ChoiceField) else self.source.value

        if '0-0-0-0' in filters:
            items = model.objects.all()
        else:
            items = model.objects.filter(uuid__in=filters)

        return items

    def getIntervalInHours(self):
        return {'hour': 1, 'day': 24, 'week': 24 * 7, 'month': 24 * 30}[self.interval.value]

    def getIntervalsList(self) -> list[tuple[datetime.datetime, datetime.datetime]]:
        intervals: list[tuple[datetime.datetime, datetime.datetime]] = []
        # Convert start and end dates to datetime objects from date objects
        start = datetime.datetime.combine(self.startingDate(), datetime.time.min)
        to = datetime.datetime.combine(self.endingDate(), datetime.time.max)
        while start < to:
            if self.interval.value == 'hour':
                intervals.append((start, start + datetime.timedelta(hours=1)))
                start += datetime.timedelta(hours=1)
            elif self.interval.value == 'day':
                intervals.append((start, start + datetime.timedelta(days=1)))
                start += datetime.timedelta(days=1)
            elif self.interval.value == 'week':
                intervals.append((start, start + datetime.timedelta(days=7)))
                start += datetime.timedelta(days=7)
            elif self.interval.value == 'month':
                next = (start + datetime.timedelta(days=32)).replace(day=1)
                intervals.append((start, next))
                start = next

        logger.debug('Intervals: %s', intervals)
        return intervals

    def adjustDate(self, d: datetime.date, isEndingDate: bool) -> datetime.date:
        if self.interval.value in ('hour', 'day'):
            return d
        if self.interval.value == 'week':
            return (d - datetime.timedelta(days=d.weekday())).replace()
        if self.interval.value == 'month':
            if not isEndingDate:
                return d.replace(day=1)
            return (d + datetime.timedelta(days=32)).replace(day=1) - datetime.timedelta(days=1)
        return d

    def formatDatetimeAsString(self, d: datetime.date) -> str:
        if self.interval.value in ('hour', 'day'):
            return d.strftime('%Y-%b-%d %H:%M:%S')
        if self.interval.value == 'week':
            return d.strftime('%Y-%b-%d')
        if self.interval.value == 'month':
            return d.strftime('%Y-%b')
        return d.strftime('%Y-%b-%d %H:%M:%S')

    def startingDate(self) -> datetime.date:
        return self.adjustDate(self.date_start.as_date(), False)

    def endingDate(self) -> datetime.date:
        return self.adjustDate(self.date_end.as_date(), True)
