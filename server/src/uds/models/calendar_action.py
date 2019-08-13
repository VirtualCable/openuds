# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
#
# Copyright (c) 2016-2019 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import json
import logging
import typing


from django.utils.translation import ugettext_lazy as _
from django.db import models

from uds.core.util import (calendar, log)

from .calendar import Calendar
from .uuid_model import UUIDModel
from .util import getSqlDatetime
from .ServicesPool import ServicePool
from .transport import Transport
from .authenticator import Authenticator
# from django.utils.translation import ugettext_lazy as _, ugettext


logger = logging.getLogger(__name__)

# Current posible actions
# Each line describes:
#
CALENDAR_ACTION_PUBLISH = {'id': 'PUBLISH', 'description': _('Publish'), 'params': ()}
CALENDAR_ACTION_CACHE_L1 = {'id': 'CACHEL1', 'description': _('Set cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache size'), 'default': '1'},)}
CALENDAR_ACTION_CACHE_L2 = {'id': 'CACHEL2', 'description': _('Set L2 cache size'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Cache L2 size'), 'default': '1'},)}
CALENDAR_ACTION_INITIAL = {'id': 'INITIAL', 'description': _('Set initial services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Initial services'), 'default': '1'},)}
CALENDAR_ACTION_MAX = {'id': 'MAX', 'description': _('Set maximum number of services'), 'params': ({'type': 'numeric', 'name': 'size', 'description': _('Maximum services'), 'default': '10'},)}
CALENDAR_ACTION_ADD_TRANSPORT = {'id': 'ADD_TRANSPORT', 'description': _('Add a transport'), 'params': ({'type': 'transport', 'name': 'transport', 'description': _('Transport'), 'default': ''},)}
CALENDAR_ACTION_DEL_TRANSPORT = {'id': 'REMOVE_TRANSPORT', 'description': _('Remove a transport'), 'params': ({'type': 'transport', 'name': 'transport', 'description': _('Trasport'), 'default': ''},)}
CALENDAR_ACTION_ADD_GROUP = {'id': 'ADD_GROUP', 'description': _('Add a group'), 'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},)}
CALENDAR_ACTION_DEL_GROUP = {'id': 'REMOVE_GROUP', 'description': _('Remove a group'), 'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},)}

CALENDAR_ACTION_DICT: typing.Dict[str, typing.Dict] = {c['id']: c for c in (
    CALENDAR_ACTION_PUBLISH, CALENDAR_ACTION_CACHE_L1,
    CALENDAR_ACTION_CACHE_L2, CALENDAR_ACTION_INITIAL,
    CALENDAR_ACTION_MAX,
    CALENDAR_ACTION_ADD_TRANSPORT, CALENDAR_ACTION_DEL_TRANSPORT,
    CALENDAR_ACTION_ADD_GROUP, CALENDAR_ACTION_DEL_GROUP
)}


class CalendarAction(UUIDModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    service_pool = models.ForeignKey(ServicePool, on_delete=models.CASCADE)
    action = models.CharField(max_length=64, default='')
    at_start = models.BooleanField(default=False)  # If false, action is done at end of event
    events_offset = models.IntegerField(default=0)  # In minutes
    params = models.CharField(max_length=1024, default='')
    # Not to be edited, just to be used as indicators for executions
    last_execution = models.DateTimeField(default=None, db_index=True, null=True, blank=True)
    next_execution = models.DateTimeField(default=None, db_index=True, null=True, blank=True)

    class Meta:
        """
        Meta class to declare db table
        """
        db_table = 'uds_cal_action'
        app_label = 'uds'

    @property
    def offset(self):
        return datetime.timedelta(minutes=self.events_offset)

    @property
    def prettyParams(self) -> str:
        try:
            ca = CALENDAR_ACTION_DICT.get(self.action)

            if ca is None:
                raise Exception('{} not in action dict'.format(self.action))

            params = json.loads(self.params)
            res = []
            for p in ca['params']:
                val = params[p['name']]
                pp = '{}='.format(p['name'])
                # Transport
                if p['type'] == 'transport':
                    try:
                        pp += Transport.objects.get(uuid=val).name
                    except Exception:
                        pp += '(invalid)'
                # Groups
                elif p['type'] == 'group':
                    try:
                        auth, grp = params[p['name']].split('@')
                        auth = Authenticator.objects.get(uuid=auth)
                        grp = auth.groups.get(uuid=grp)
                        pp += grp.name + '@' + auth.name
                    except Exception:
                        pp += '(invalid)'
                else:
                    pp += str(val)
                res.append(pp)
            return ','.join(res)
        except Exception:
            logger.exception('error')
            return '(invalid action)'

    def execute(self, save: bool = True) -> None:  # pylinf: disable=too-many-branches, too-many-statements
        """Executes the calendar action

        Keyword Arguments:
            save {bool} -- [If save this action after execution (will regen next execution time)] (default: {True})
        """
        logger.debug('Executing action')
        self.last_execution = getSqlDatetime()
        params = json.loads(self.params)

        saveServicePool = save

        def sizeVal() -> int:
            v = int(params['size'])
            return v if v >= 0 else 0

        executed = False
        if CALENDAR_ACTION_CACHE_L1['id'] == self.action:
            self.service_pool.cache_l1_srvs = sizeVal()
            executed = True
        elif CALENDAR_ACTION_CACHE_L2['id'] == self.action:
            self.service_pool.cache_l2_srvs = sizeVal()
            executed = True
        elif CALENDAR_ACTION_INITIAL['id'] == self.action:
            self.service_pool.initial_srvs = sizeVal()
            executed = True
        elif CALENDAR_ACTION_MAX['id'] == self.action:
            self.service_pool.max_srvs = sizeVal()
            executed = True
        elif CALENDAR_ACTION_PUBLISH['id'] == self.action:
            self.service_pool.publish(changeLog='Scheduled publication action')
            saveServicePool = False
            executed = True
        else:
            caTransports = (CALENDAR_ACTION_ADD_TRANSPORT['id'], CALENDAR_ACTION_DEL_TRANSPORT['id'])
            caGroups = (CALENDAR_ACTION_ADD_GROUP['id'], CALENDAR_ACTION_DEL_GROUP['id'])
            if self.action in caTransports:
                try:
                    t = Transport.objects.get(uuid=params['transport'])
                    if self.action == caTransports[0]:
                        self.service_pool.transports.add(t)
                    else:
                        self.service_pool.transports.remove(t)
                    executed = True
                except Exception:
                    self.service_pool.log('Scheduled action not executed because transport is not available anymore')
                saveServicePool = False
            elif self.action in caGroups:
                try:
                    auth, grp = params['group'].split('@')
                    grp = Authenticator.objects.get(uuid=auth).groups.get(uuid=grp)
                    if self.action == caGroups[0]:
                        self.service_pool.assignedGroups.add(grp)
                    else:
                        self.service_pool.assignedGroups.remove(grp)
                    executed = True
                except Exception:
                    self.service_pool.log('Scheduled action not executed because group is not available anymore')
                saveServicePool = False

        if executed:
            try:
                self.service_pool.log(
                    'Executed action {} [{}]'.format(
                        CALENDAR_ACTION_DICT.get(self.action, {})['description'], self.prettyParams
                    ),
                    level=log.INFO
                )
            except Exception:
                # Avoid invalid ACTIONS errors on log
                self.service_pool.log('Action {} is not a valid scheduled action! please, remove it from your list.'.format(self.action))

        # On save, will regenerate nextExecution
        if save:
            self.save()

        if saveServicePool:
            self.service_pool.save()

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        self.next_execution = calendar.CalendarChecker(self.calendar).nextEvent(checkFrom=self.last_execution, startEvent=self.at_start, offset=self.offset)

        super().save(force_insert, force_update, using, update_fields)

    def __str__(self):
        return 'Calendar of {}, last_execution = {}, next execution = {}, action = {}, params = {}'.format(
            self.service_pool.name, self.last_execution, self.next_execution, self.action, self.params
        )
