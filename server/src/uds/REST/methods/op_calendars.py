# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import datetime
import json
import logging
import typing

from django.utils.translation import gettext as _

from uds.core import types, consts
from uds.core.types.rest import Table
from uds.core.util import log, ensure, ui as ui_utils
from uds.core.util.model import process_uuid
from uds import models
from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

ALLOW = 'ALLOW'
DENY = 'DENY'


class AccessCalendarItem(types.rest.BaseRestItem):
    id: str
    calendar_id: str
    calendar: str
    access: str
    priority: int


class AccessCalendars(DetailHandler[AccessCalendarItem]):
    @staticmethod
    def as_dict(item: 'models.CalendarAccess|models.CalendarAccessMeta') -> AccessCalendarItem:
        return {
            'id': item.uuid,
            'calendar_id': item.calendar.uuid,
            'calendar': item.calendar.name,
            'access': item.access,
            'priority': item.priority,
        }

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult[AccessCalendarItem]:
        # parent can be a ServicePool or a metaPool
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)

        try:
            if not item:
                return [AccessCalendars.as_dict(i) for i in parent.calendarAccess.all()]
            return AccessCalendars.as_dict(parent.calendarAccess.get(uuid=process_uuid(item)))
        except Exception as e:
            logger.exception('err: %s', item)
            raise self.invalid_item_response() from e

    def get_table(self, parent: 'Model') -> types.rest.Table:
        return (
            ui_utils.TableBuilder(_('Access calendars'))
            .numeric_column('priority', _('Priority'))
            .text_column('calendar', _('Calendar'))
            .text_column('access', _('Access'))
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)
        # If already exists
        uuid = process_uuid(item) if item is not None else None

        try:
            calendar: models.Calendar = models.Calendar.objects.get(
                uuid=process_uuid(self._params['calendar_id'])
            )
            access: str = self._params['access'].upper()
            if access not in (ALLOW, DENY):
                raise Exception()
        except Exception as e:
            raise self.invalid_request_response(_('Invalid parameters on request')) from e
        priority = int(self._params['priority'])

        if uuid is not None:
            calendar_access = parent.calendarAccess.get(uuid=uuid)
            calendar_access.calendar = calendar
            calendar_access.access = access
            calendar_access.priority = priority
            calendar_access.save(update_fields=['calendar', 'access', 'priority'])
        else:
            calendar_access = parent.calendarAccess.create(calendar=calendar, access=access, priority=priority)

        log.log(
            parent,
            types.log.LogLevel.INFO,
            f'{"Added" if uuid is None else "Updated"} access calendar {calendar.name}/{access} by {self._user.pretty_name}',
            types.log.LogSource.ADMIN,
        )

        return {'id': calendar_access.uuid}

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = typing.cast(typing.Union['models.ServicePool', 'models.MetaPool'], parent)
        calendar_access = parent.calendarAccess.get(uuid=process_uuid(self._args[0]))
        log_str = f'Removed access calendar {calendar_access.calendar.name} by {self._user.pretty_name}'
        calendar_access.delete()

        log.log(parent, types.log.LogLevel.INFO, log_str, types.log.LogSource.ADMIN)


class ActionCalendarItem(types.rest.BaseRestItem):
    id: str
    calendar_id: str
    calendar: str
    action: str
    description: str
    at_start: bool
    events_offset: int
    params: dict[str, typing.Any]
    pretty_params: str
    next_execution: typing.Optional[datetime.datetime]
    last_execution: typing.Optional[datetime.datetime]


class ActionsCalendars(DetailHandler[ActionCalendarItem]):
    """
    Processes the transports detail requests of a Service Pool
    """

    CUSTOM_METHODS = [
        'execute',
    ]

    @staticmethod
    def as_dict(item: 'models.CalendarAction') -> ActionCalendarItem:
        action = consts.calendar.CALENDAR_ACTION_DICT.get(item.action)
        descrption = action.get('description') if action is not None else ''
        params = json.loads(item.params)
        return {
            'id': item.uuid,
            'calendar_id': item.calendar.uuid,
            'calendar': item.calendar.name,
            'action': item.action,
            'description': descrption,
            'at_start': item.at_start,
            'events_offset': item.events_offset,
            'params': params,
            'pretty_params': item.pretty_params,
            'next_execution': item.next_execution,
            'last_execution': item.last_execution,
        }

    def get_items(
        self, parent: 'Model', item: typing.Optional[str]
    ) -> types.rest.ItemsResult[ActionCalendarItem]:
        parent = ensure.is_instance(parent, models.ServicePool)
        try:
            if item is None:
                return [ActionsCalendars.as_dict(i) for i in parent.calendaraction_set.all()]
            i = parent.calendaraction_set.get(uuid=process_uuid(item))
            return ActionsCalendars.as_dict(i)
        except Exception as e:
            raise self.invalid_item_response() from e

    def get_table(self, parent: 'Model') -> Table:
        return (
            ui_utils.TableBuilder(_('Scheduled actions'))
            .text_column('calendar', _('Calendar'))
            .text_column('description', _('Action'))
            .text_column('pretty_params', _('Parameters'))
            .dict_column('at_start', _('Relative to'), dct={True: _('Start'), False: _('End')})
            .text_column('events_offset', _('Time offset'))
            .datetime_column('next_execution', _('Next execution'))
            .datetime_column('last_execution', _('Last execution'))
            .build()
        )

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServicePool)
        # If already exists
        uuid = process_uuid(item) if item is not None else None

        calendar = models.Calendar.objects.get(uuid=process_uuid(self._params['calendar_id']))
        action = self._params['action'].upper()
        if action not in consts.calendar.CALENDAR_ACTION_DICT:
            raise self.invalid_request_response()
        events_offset = int(self._params['events_offset'])
        at_start = self._params['at_start'] not in ('false', False, '0', 0)
        params = json.dumps(self._params['params'])

        # logger.debug('Got parameters: {} {} {} {} ----> {}'.format(calendar, action, events_offset, at_start, params))
        log_string = (
            f'{"Added" if uuid is None else "Updated"} scheduled action '
            f'{calendar.name},{action},{events_offset},{"start" if at_start else "end"},{params} '
            f'by {self._user.pretty_name}'
        )

        if uuid is not None:
            calendar_action = models.CalendarAction.objects.get(uuid=uuid)
            calendar_action.calendar = calendar
            calendar_action.service_pool = parent
            calendar_action.action = action
            calendar_action.at_start = at_start
            calendar_action.events_offset = events_offset
            calendar_action.params = params
            calendar_action.save()
        else:
            calendar_action = models.CalendarAction.objects.create(
                calendar=calendar,
                service_pool=parent,
                action=action,
                at_start=at_start,
                events_offset=events_offset,
                params=params,
            )

        log.log(parent, types.log.LogLevel.INFO, log_string, types.log.LogSource.ADMIN)

        return {'id': calendar_action.uuid}

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, models.ServicePool)
        calendar_action = models.CalendarAction.objects.get(uuid=process_uuid(self._args[0]))
        log_str = (
            f'Removed scheduled action "{calendar_action.calendar.name},'
            f'{calendar_action.action},{calendar_action.events_offset},'
            f'{calendar_action.at_start and "Start" or "End"},'
            f'{calendar_action.params}" by {self._user.pretty_name}'
        )

        calendar_action.delete()

        log.log(parent, types.log.LogLevel.INFO, log_str, types.log.LogSource.ADMIN)

    def execute(self, parent: 'Model', item: str) -> typing.Any:
        parent = ensure.is_instance(parent, models.ServicePool)
        logger.debug('Launching action')
        uuid = process_uuid(item)
        calendar_action: models.CalendarAction = models.CalendarAction.objects.get(uuid=uuid)
        self.check_access(calendar_action, types.permissions.PermissionType.MANAGEMENT)

        log_str = (
            f'Launched scheduled action "{calendar_action.calendar.name},'
            f'{calendar_action.action},{calendar_action.events_offset},'
            f'{calendar_action.at_start and "Start" or "End"},'
            f'{calendar_action.params}" by {self._user.pretty_name}'
        )

        log.log(parent, types.log.LogLevel.INFO, log_str, types.log.LogSource.ADMIN)
        calendar_action.execute()

        return self.success()
