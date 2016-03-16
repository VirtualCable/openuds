# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

# pylint: disable=too-many-public-methods

from __future__ import unicode_literals

from django.utils.translation import ugettext as _


from uds.models import CalendarAccess, CalendarAction, Calendar
from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.REST.model import DetailHandler
from uds.REST import ResponseError
from uds.core.util import permissions



import logging

logger = logging.getLogger(__name__)

ALLOW = 'ALLOW'
DENY = 'DENY'


class AccessCalendars(DetailHandler):
    '''
    Processes the transports detail requests of a Service Pool
    '''
    @staticmethod
    def as_dict(item):
        return {
            'id': item.uuid,
            'calendarId': item.calendar.uuid,
            'name': item.calendar.name,
            'access': item.access,
            'priority': item.priority,
        }

    def getItems(self, parent, item):
        try:
            if item is None:
                return [AccessCalendars.as_dict(i) for i in parent.calendaraccess_set.all()]
            else:
                i = CalendarAccess.objects.get(uuid=processUuid(item))
                return AccessCalendars.as_dict(i)
        except Exception:
            self.invalidItemException()


    def getTitle(self, parent):
        return _('Access restrictions by calendar')

    def getFields(self, parent):
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'name': {'title': _('Name')}},
            {'access': {'title': _('Access')}},
        ]

    def saveItem(self, parent, item):
        # If already exists
        uuid = processUuid(self._params['id']) if 'id' in self._params else None

        calendar = Calendar.objects.get(uuid=processUuid(self._params['calendarId']))
        access = self._params['access'].upper()
        priority = int(self._params['priority'])

        if uuid is not None:
            calAccess = CalendarAccess.objects.get(uuid=uuid)
            calAccess.calendar = calendar
            calAccess.servicePool = parent
            calAccess.access = access
            calAccess.priority = priority
            calAccess.save()
        else:
            CalendarAccess.objects.create(calendar=calendar, servicePool=parent, access=access, priority=priority)

        return self.success()

    def deleteItem(self, parent, item):
        CalendarAccess.objects.get(uuid=processUuid(self._args[0])).delete()



class ActionsCalendars(DetailHandler):
    '''
    Processes the transports detail requests of a Service Pool
    '''
    @staticmethod
    def as_dict(item):
        return {
            'id': item.uuid,
            'calendarId': item.calendar.uuid,
            'name': item.calendar.name,
            'action': item.action,
            'atStart': item.atStart,
            'offset': item.eventOffset,
            'params': item.params
        }

    def getItems(self, parent, item):
        try:
            if item is None:
                return [ActionsCalendars.as_dict(i) for i in parent.calendaraction_set.all()]
            else:
                i = CalendarAction.objects.get(uuid=processUuid(item))
                return ActionsCalendars.as_dict(i)
        except Exception:
            self.invalidItemException()


    def getTitle(self, parent):
        return _('Scheduled actions')

    def getFields(self, parent):
        return [
            {'name': {'title': _('Name')}},
            {'action': {'title': _('Action')}},
            {'atStart': {'title': _('Referer')}},
            {'offset': {'title': _('Time offset')}},
        ]

    def saveItem(self, parent, item):
        # If already exists
        uuid = processUuid(self._params['id']) if 'id' in self._params else None

        calendar = Calendar.objects.get(uuid=processUuid(self._params['calendarId']))
        action = self._params['action'].upper()
        eventOffset = int(self._params['eventOffset'])
        atStart = (self._params['atStart'] == 'true')

        if uuid is not None:
            calAction = CalendarAction.objects.get(uuid=uuid)
            calAction.calendar = calendar
            calAction.servicePool = parent
            calAction.action = action
            calAction.atStart = atStart
            calAction.eventOffset = eventOffset
            calAction.save()
        else:
            CalendarAction.objects.create(calendar=calendar, servicePool=parent, action=action, atStart=atStart, eventOffset=eventOffset)

        return self.success()

    def deleteItem(self, parent, item):
        CalendarAction.objects.get(uuid=processUuid(self._args[0])).delete()
