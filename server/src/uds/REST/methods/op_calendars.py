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

from django.utils.translation import gettext as _

from uds.models import Calendar, CalendarAction
from uds.models.calendar_action import CALENDAR_ACTION_DICT
from uds.core.util import log, permissions
from uds.core.util.model import processUuid

from uds.REST.model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import CalendarAccess, ServicePool

logger = logging.getLogger(__name__)

ALLOW = 'ALLOW'
DENY = 'DENY'


class AccessCalendars(DetailHandler):
    @staticmethod
    def as_dict(item: 'CalendarAccess'):
        return {
            'id': item.uuid,
            'calendarId': item.calendar.uuid,
            'calendar': item.calendar.name,
            'access': item.access,
            'priority': item.priority,
        }

    def getItems(self, parent: 'ServicePool', item: typing.Optional[str]):
        try:
            if not item:
                return [AccessCalendars.as_dict(i) for i in parent.calendarAccess.all()]
            return AccessCalendars.as_dict(
                parent.calendarAccess.get(uuid=processUuid(item))
            )
        except Exception as e:
            logger.exception('err: %s', item)
            raise self.invalidItemException() from e

    def getTitle(self, parent: 'ServicePool'):
        return _('Access restrictions by calendar')

    def getFields(self, parent: 'ServicePool') -> typing.List[typing.Any]:
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'calendar': {'title': _('Calendar')}},
            {'access': {'title': _('Access')}},
        ]

    def saveItem(self, parent: 'ServicePool', item: typing.Optional[str]) -> None:
        # If already exists
        uuid = processUuid(item) if item is not None else None

        try:
            calendar: Calendar = Calendar.objects.get(
                uuid=processUuid(self._params['calendarId'])
            )
            access: str = self._params['access'].upper()
            if access not in (ALLOW, DENY):
                raise Exception()
        except Exception as e:
            raise self.invalidRequestException(
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

        log.doLog(
            parent,
            log.LogLevel.INFO,
            f'{"Added" if uuid is None else "Updated"} access calendar {calendar.name}/{access} by {self._user.pretty_name}',
            log.LogSource.ADMIN,
        )

    def deleteItem(self, parent: 'ServicePool', item: str) -> None:
        calendarAccess = parent.calendarAccess.get(uuid=processUuid(self._args[0]))
        logStr = f'Removed access calendar {calendarAccess.calendar.name} by {self._user.pretty_name}'
        calendarAccess.delete()

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)


class ActionsCalendars(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    custom_methods = [
        'execute',
    ]

    @staticmethod
    def as_dict(item: 'CalendarAction') -> typing.Dict[str, typing.Any]:
        action = CALENDAR_ACTION_DICT.get(item.action, {})
        params = json.loads(item.params)
        return {
            'id': item.uuid,
            'calendarId': item.calendar.uuid,
            'calendar': item.calendar.name,
            'action': item.action,
            'actionDescription': action.get('description'),
            'atStart': item.at_start,
            'eventsOffset': item.events_offset,
            'params': params,
            'pretty_params': item.prettyParams,
            'nextExecution': item.next_execution,
            'lastExecution': item.last_execution,
        }

    def getItems(self, parent: 'ServicePool', item: typing.Optional[str]):
        try:
            if item is None:
                return [
                    ActionsCalendars.as_dict(i) for i in parent.calendaraction_set.all()
                ]
            i = parent.calendaraction_set.get(uuid=processUuid(item))
            return ActionsCalendars.as_dict(i)
        except Exception as e:
            raise self.invalidItemException() from e

    def getTitle(self, parent: 'ServicePool'):
        return _('Scheduled actions')

    def getFields(self, parent: 'ServicePool') -> typing.List[typing.Any]:
        return [
            {'calendar': {'title': _('Calendar')}},
            {'actionDescription': {'title': _('Action')}},
            {'pretty_params': {'title': _('Parameters')}},
            {'atStart': {'title': _('Relative to')}},
            {'eventsOffset': {'title': _('Time offset')}},
            {'nextExecution': {'title': _('Next execution'), 'type': 'datetime'}},
            {'lastExecution': {'title': _('Last execution'), 'type': 'datetime'}},
        ]

    def saveItem(self, parent: 'ServicePool', item: typing.Optional[str]) -> None:
        # If already exists
        uuid = processUuid(item) if item is not None else None

        calendar = Calendar.objects.get(uuid=processUuid(self._params['calendarId']))
        action = self._params['action'].upper()
        if action not in CALENDAR_ACTION_DICT:
            raise self.invalidRequestException()
        eventsOffset = int(self._params['eventsOffset'])
        atStart = self._params['atStart'] not in ('false', False, '0', 0)
        params = json.dumps(self._params['params'])

        # logger.debug('Got parameters: {} {} {} {} ----> {}'.format(calendar, action, eventsOffset, atStart, params))
        logStr = (
            f'{"Added" if uuid is None else "Updated"} scheduled action '
            f'{calendar.name},{action},{eventsOffset},{"start" if atStart else "end"},{params} '
            f'by {self._user.pretty_name}'
        )

        if uuid is not None:
            calAction = CalendarAction.objects.get(uuid=uuid)
            calAction.calendar = calendar  # type: ignore
            calAction.service_pool = parent  # type: ignore
            calAction.action = action
            calAction.at_start = atStart
            calAction.events_offset = eventsOffset
            calAction.params = params
            calAction.save()
        else:
            CalendarAction.objects.create(
                calendar=calendar,
                service_pool=parent,
                action=action,
                at_start=atStart,
                events_offset=eventsOffset,
                params=params,
            )

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    def deleteItem(self, parent: 'ServicePool', item: str) -> None:
        calendarAction = CalendarAction.objects.get(uuid=processUuid(self._args[0]))
        logStr = (
            f'Removed scheduled action "{calendarAction.calendar.name},'
            f'{calendarAction.action},{calendarAction.events_offset},'
            f'{calendarAction.at_start and "Start" or "End"},'
            f'{calendarAction.params}" by {self._user.pretty_name}'
        )

        calendarAction.delete()

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    def execute(self, parent: 'ServicePool', item: str):
        logger.debug('Launching action')
        uuid = processUuid(item)
        calendarAction: CalendarAction = CalendarAction.objects.get(uuid=uuid)
        self.ensureAccess(calendarAction, permissions.PermissionType.MANAGEMENT)

        logStr = (
            f'Launched scheduled action "{calendarAction.calendar.name},'
            f'{calendarAction.action},{calendarAction.events_offset},'
            f'{calendarAction.at_start and "Start" or "End"},'
            f'{calendarAction.params}" by {self._user.pretty_name}'
        )

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)
        calendarAction.execute()

        return self.success()
