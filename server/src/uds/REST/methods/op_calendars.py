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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import json
import logging
import typing
import collections.abc

from django.utils.translation import gettext as _

from uds.core import types, consts
from uds.core.util import log, ensure
from uds.core.util.model import process_uuid
from uds.models import Calendar, CalendarAction, CalendarAccess, ServicePool
from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

ALLOW = 'ALLOW'
DENY = 'DENY'


class AccessCalendars(DetailHandler):
    @staticmethod
    def as_dict(item: 'CalendarAccess'):
        return {
            'id': item.uuid,
            'calendar_id': item.calendar.uuid,
            'calendar': item.calendar.name,
            'access': item.access,
            'priority': item.priority,
        }

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, ServicePool)
        try:
            if not item:
                return [AccessCalendars.as_dict(i) for i in parent.calendarAccess.all()]
            return AccessCalendars.as_dict(
                parent.calendarAccess.get(uuid=process_uuid(item))
            )
        except Exception as e:
            logger.exception('err: %s', item)
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model'):
        return _('Access restrictions by calendar')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'calendar': {'title': _('Calendar')}},
            {'access': {'title': _('Access')}},
        ]

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, ServicePool)
        # If already exists
        uuid = process_uuid(item) if item is not None else None

        try:
            calendar: Calendar = Calendar.objects.get(
                uuid=process_uuid(self._params['calendar_id'])
            )
            access: str = self._params['access'].upper()
            if access not in (ALLOW, DENY):
                raise Exception()
        except Exception as e:
            raise self.invalid_request_response(
                _('Invalid parameters on request')
            ) from e
        priority = int(self._params['priority'])

        if uuid is not None:
            calAccess: 'CalendarAccess' = parent.calendarAccess.get(uuid=uuid)
            calAccess.calendar = calendar  # type: ignore
            calAccess.service_pool = parent  # type: ignore
            calAccess.access = access
            calAccess.priority = priority
            calAccess.save()
        else:
            parent.calendarAccess.create(
                calendar=calendar, access=access, priority=priority
            )

        log.log(
            parent,
            log.LogLevel.INFO,
            f'{"Added" if uuid is None else "Updated"} access calendar {calendar.name}/{access} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, ServicePool)
        calendarAccess = parent.calendarAccess.get(uuid=process_uuid(self._args[0]))
        logStr = f'Removed access calendar {calendarAccess.calendar.name} by {self._user.pretty_name}'
        calendarAccess.delete()

        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)


class ActionsCalendars(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    custom_methods = [
        'execute',
    ]

    @staticmethod
    def as_dict(item: 'CalendarAction') -> dict[str, typing.Any]:
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
            'pretty_params': item.prettyParams,
            'next_execution': item.next_execution,
            'last_execution': item.last_execution,
        }

    def get_items(self, parent: 'Model', item: typing.Optional[str]):
        parent = ensure.is_instance(parent, ServicePool)
        try:
            if item is None:
                return [
                    ActionsCalendars.as_dict(i) for i in parent.calendaraction_set.all()
                ]
            i = parent.calendaraction_set.get(uuid=process_uuid(item))
            return ActionsCalendars.as_dict(i)
        except Exception as e:
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model'):
        return _('Scheduled actions')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {'calendar': {'title': _('Calendar')}},
            {'description': {'title': _('Action')}},
            {'pretty_params': {'title': _('Parameters')}},
            {'at_start': {'title': _('Relative to')}},
            {'events_offset': {'title': _('Time offset')}},
            {'next_execution': {'title': _('Next execution'), 'type': 'datetime'}},
            {'last_execution': {'title': _('Last execution'), 'type': 'datetime'}},
        ]

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> None:
        parent = ensure.is_instance(parent, ServicePool)
        # If already exists
        uuid = process_uuid(item) if item is not None else None

        calendar = Calendar.objects.get(uuid=process_uuid(self._params['calendar_id']))
        action = self._params['action'].upper()
        if action not in consts.calendar.CALENDAR_ACTION_DICT:
            raise self.invalid_request_response()
        events_offset = int(self._params['events_offset'])
        at_start = self._params['at_start'] not in ('false', False, '0', 0)
        params = json.dumps(self._params['params'])

        # logger.debug('Got parameters: {} {} {} {} ----> {}'.format(calendar, action, events_offset, at_start, params))
        logStr = (
            f'{"Added" if uuid is None else "Updated"} scheduled action '
            f'{calendar.name},{action},{events_offset},{"start" if at_start else "end"},{params} '
            f'by {self._user.pretty_name}'
        )

        if uuid is not None:
            calAction = CalendarAction.objects.get(uuid=uuid)
            calAction.calendar = calendar  # type: ignore
            calAction.service_pool = parent  # type: ignore
            calAction.action = action
            calAction.at_start = at_start
            calAction.events_offset = events_offset
            calAction.params = params
            calAction.save()
        else:
            CalendarAction.objects.create(
                calendar=calendar,
                service_pool=parent,
                action=action,
                at_start=at_start,
                events_offset=events_offset,
                params=params,
            )

        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, ServicePool)
        calendarAction = CalendarAction.objects.get(uuid=process_uuid(self._args[0]))
        logStr = (
            f'Removed scheduled action "{calendarAction.calendar.name},'
            f'{calendarAction.action},{calendarAction.events_offset},'
            f'{calendarAction.at_start and "Start" or "End"},'
            f'{calendarAction.params}" by {self._user.pretty_name}'
        )

        calendarAction.delete()

        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    def execute(self, parent: 'Model', item: str):
        parent = ensure.is_instance(parent, ServicePool)
        logger.debug('Launching action')
        uuid = process_uuid(item)
        calendarAction: CalendarAction = CalendarAction.objects.get(uuid=uuid)
        self.ensure_has_access(calendarAction, types.permissions.PermissionType.MANAGEMENT)

        logStr = (
            f'Launched scheduled action "{calendarAction.calendar.name},'
            f'{calendarAction.action},{calendarAction.events_offset},'
            f'{calendarAction.at_start and "Start" or "End"},'
            f'{calendarAction.params}" by {self._user.pretty_name}'
        )

        log.log(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)
        calendarAction.execute()

        return self.success()
