# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
#
# Copyright (c) 2016-2023 Virtual Cable S.L.
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


from django.utils.translation import gettext_lazy as _
from django.db import models

from uds.core.util import calendar
from uds.core.util import log
from uds.core.util import state
from uds.core.managers.user_service import UserServiceManager
from uds.core import services

from .calendar import Calendar
from .uuid_model import UUIDModel
from ..core.util.model import getSqlDatetime
from .service_pool import ServicePool
from .transport import Transport
from .authenticator import Authenticator

# from django.utils.translation import gettext_lazy as _, gettext


logger = logging.getLogger(__name__)

# Current posible actions
#
CALENDAR_ACTION_PUBLISH: typing.Dict[str, typing.Any] = {
    'id': 'PUBLISH',
    'description': _('Publish'),
    'params': (),
}
CALENDAR_ACTION_CACHE_L1: typing.Dict[str, typing.Any] = {
    'id': 'CACHEL1',
    'description': _('Set cache size'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Cache size'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_CACHE_L2: typing.Dict[str, typing.Any] = {
    'id': 'CACHEL2',
    'description': _('Set L2 cache size'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Cache L2 size'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_INITIAL: typing.Dict[str, typing.Any] = {
    'id': 'INITIAL',
    'description': _('Set initial services'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Initial services'),
            'default': '1',
        },
    ),
}
CALENDAR_ACTION_MAX: typing.Dict[str, typing.Any] = {
    'id': 'MAX',
    'description': _('Set maximum number of services'),
    'params': (
        {
            'type': 'numeric',
            'name': 'size',
            'description': _('Maximum services'),
            'default': '10',
        },
    ),
}
CALENDAR_ACTION_ADD_TRANSPORT: typing.Dict[str, typing.Any] = {
    'id': 'ADD_TRANSPORT',
    'description': _('Add a transport'),
    'params': (
        {
            'type': 'transport',
            'name': 'transport',
            'description': _('Transport'),
            'default': '',
        },
    ),
}
CALENDAR_ACTION_DEL_TRANSPORT: typing.Dict[str, typing.Any] = {
    'id': 'REMOVE_TRANSPORT',
    'description': _('Remove a transport'),
    'params': (
        {
            'type': 'transport',
            'name': 'transport',
            'description': _('Trasport'),
            'default': '',
        },
    ),
}
CALENDAR_ACTION_DEL_ALL_TRANSPORTS: typing.Dict[str, typing.Any] = {
    'id': 'REMOVE_ALL_TRANSPORTS',
    'description': _('Remove all transports'),
    'params': (),
}
CALENDAR_ACTION_ADD_GROUP: typing.Dict[str, typing.Any] = {
    'id': 'ADD_GROUP',
    'description': _('Add a group'),
    'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},),
}
CALENDAR_ACTION_DEL_GROUP: typing.Dict[str, typing.Any] = {
    'id': 'REMOVE_GROUP',
    'description': _('Remove a group'),
    'params': ({'type': 'group', 'name': 'group', 'description': _('Group'), 'default': ''},),
}
CALENDAR_ACTION_DEL_ALL_GROUPS: typing.Dict[str, typing.Any] = {
    'id': 'REMOVE_ALL_GROUPS',
    'description': _('Remove all groups'),
    'params': (),
}
CALENDAR_ACTION_IGNORE_UNUSED: typing.Dict[str, typing.Any] = {
    'id': 'IGNORE_UNUSED',
    'description': _('Sets the ignore unused'),
    'params': (
        {
            'type': 'bool',
            'name': 'state',
            'description': _('Ignore assigned and unused'),
            'default': False,
        },
    ),
}
CALENDAR_ACTION_REMOVE_USERSERVICES: typing.Dict[str, typing.Any] = {
    'id': 'REMOVE_USERSERVICES',
    'description': _('Remove ALL assigned user service. USE WITH CAUTION!'),
    'params': (),
}

CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES: typing.Dict[str, typing.Any] = {
    'id': 'STUCK_USERSERVICES',
    'description': _('Remove OLD assigned user services.'),
    'params': (
        {
            'type': 'numeric',
            'name': 'hours',
            'description': _('Time in hours before considering the user service is OLD.'),
            'default': '72',
        },
    ),
}

CALENDAR_ACTION_CLEAN_CACHE_L1: typing.Dict[str, typing.Any] = {
    'id': 'CLEAN_CACHE_L1',
    'description': _('Clean L1 cache'),
    'params': (),
}

CALENDAR_ACTION_CLEAN_CACHE_L2: typing.Dict[str, typing.Any] = {
    'id': 'CLEAN_CACHE_L2',
    'description': _('Clean L2 cache'),
    'params': (),
}


CALENDAR_ACTION_DICT: typing.Dict[str, typing.Dict] = {
    c['id']: c
    for c in (
        CALENDAR_ACTION_PUBLISH,
        CALENDAR_ACTION_CACHE_L1,
        CALENDAR_ACTION_CACHE_L2,
        CALENDAR_ACTION_INITIAL,
        CALENDAR_ACTION_MAX,
        CALENDAR_ACTION_ADD_TRANSPORT,
        CALENDAR_ACTION_DEL_TRANSPORT,
        CALENDAR_ACTION_DEL_ALL_TRANSPORTS,
        CALENDAR_ACTION_ADD_GROUP,
        CALENDAR_ACTION_DEL_GROUP,
        CALENDAR_ACTION_DEL_ALL_GROUPS,
        CALENDAR_ACTION_IGNORE_UNUSED,
        CALENDAR_ACTION_REMOVE_USERSERVICES,
        CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES,
        CALENDAR_ACTION_CLEAN_CACHE_L1,
        CALENDAR_ACTION_CLEAN_CACHE_L2,
    )
}


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

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[CalendarAction]'

    class Meta:  # pylint: disable=too-few-public-methods
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
                raise Exception(f'Action {self.action} not found')

            params = json.loads(self.params)
            res = []
            for p in ca['params']:
                val = params[p['name']]
                pp = f'{p["name"]}='
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

    def execute(self, save: bool = True) -> None:  # pylint: disable=too-many-branches, too-many-statements
        """Executes the calendar action

        Keyword Arguments:
            save {bool} -- [If save this action after execution (will regen next execution time)] (default: {True})
        """
        logger.debug('Executing action')
        # If restrained pool, skip this execution (will rery later, not updated)
        if not self.service_pool.isUsable():
            logger.info(
                'Execution of task for %s due to contained state (restrained, in maintenance or removing)',
                self.service_pool.name,
            )
            return

        self.last_execution = getSqlDatetime()
        params = json.loads(self.params)

        saveServicePool = save

        def numVal(field: str) -> int:
            v = int(params[field])
            return v if v >= 0 else 0

        # Actions related to calendar actions
        def set_l1_cache() -> None:
            self.service_pool.cache_l1_srvs = numVal('size')

        def set_l2_cache() -> None:
            self.service_pool.cache_l2_srvs = numVal('size')

        def set_initial() -> None:
            self.service_pool.initial_srvs = numVal('size')

        def set_max() -> None:
            self.service_pool.max_srvs = numVal('size')

        def publish() -> None:
            nonlocal saveServicePool
            self.service_pool.publish()
            saveServicePool = False

        def ignores_unused() -> None:
            self.service_pool.ignores_unused = params['state'] in ('true', '1', True)

        def remove_userservices() -> None:
            # 1.- Remove usable assigned services (Ignore "creating ones", just for created)
            for userService in self.service_pool.assignedUserServices().filter(state=state.State.USABLE):
                userService.remove()

        def remove_stuck_userservice() -> None:
            # 1.- Remove stuck assigned services (Ignore "creating ones", just for created)
            since = getSqlDatetime() - datetime.timedelta(hours=numVal('hours'))
            for userService in self.service_pool.assignedUserServices().filter(
                state_date__lt=since, state=state.State.USABLE
            ):
                userService.remove()

        def del_all_transport() -> None:
            # 2.- Remove all transports
            self.service_pool.transports.clear()

        def del_all_groups() -> None:
            # 3.- Remove all groups
            self.service_pool.assignedGroups.clear()

        def clear_cache() -> None:
            # 4.- Remove all cache_l1_srvs
            for i in self.service_pool.cachedUserServices().filter(
                UserServiceManager().getCacheStateFilter(
                    self.service_pool,
                    services.UserService.L1_CACHE
                    if self.action == CALENDAR_ACTION_CLEAN_CACHE_L1['id']
                    else services.UserService.L2_CACHE,
                )
            ):
                i.remove()

        def add_del_transport() -> None:
            try:
                t = Transport.objects.get(uuid=params['transport'])
                if self.action == CALENDAR_ACTION_ADD_TRANSPORT['id']:
                    self.service_pool.transports.add(t)
                else:
                    self.service_pool.transports.remove(t)
            except Exception:
                self.service_pool.log(
                    'Scheduled action not executed because transport is not available anymore'
                )

        def add_del_group() -> None:
            try:
                auth, grp = params['group'].split('@')
                grp = Authenticator.objects.get(uuid=auth).groups.get(uuid=grp)
                if self.action == CALENDAR_ACTION_ADD_GROUP['id']:
                    self.service_pool.assignedGroups.add(grp)
                else:
                    self.service_pool.assignedGroups.remove(grp)
            except Exception:
                self.service_pool.log('Scheduled action not executed because group is not available anymore')

        actions: typing.Mapping[str, typing.Tuple[typing.Callable[[], None], bool]] = {
            # Id, actions (lambda), saveServicePool (bool)
            CALENDAR_ACTION_CACHE_L1['id']: (set_l1_cache, True),
            CALENDAR_ACTION_CACHE_L2['id']: (set_l2_cache, True),
            CALENDAR_ACTION_INITIAL['id']: (set_initial, True),
            CALENDAR_ACTION_MAX['id']: (set_max, True),
            CALENDAR_ACTION_PUBLISH['id']: (publish, False),
            CALENDAR_ACTION_IGNORE_UNUSED['id']: (ignores_unused, True),
            CALENDAR_ACTION_REMOVE_USERSERVICES['id']: (remove_userservices, False),
            CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES['id']: (
                remove_stuck_userservice,
                False,
            ),
            CALENDAR_ACTION_DEL_ALL_TRANSPORTS['id']: (del_all_transport, False),
            CALENDAR_ACTION_DEL_ALL_GROUPS['id']: (del_all_groups, False),
            CALENDAR_ACTION_CLEAN_CACHE_L1['id']: (clear_cache, False),
            CALENDAR_ACTION_CLEAN_CACHE_L2['id']: (clear_cache, False),
            CALENDAR_ACTION_ADD_TRANSPORT['id']: (
                add_del_transport,
                False,
            ),
            CALENDAR_ACTION_DEL_TRANSPORT['id']: (
                add_del_transport,
                False,
            ),
            CALENDAR_ACTION_ADD_GROUP['id']: (add_del_group, False),
            CALENDAR_ACTION_DEL_GROUP['id']: (add_del_group, False),
        }

        fncAction, saveServicePool = actions.get(self.action, (None, False))

        if fncAction:
            try:
                fncAction()

                if saveServicePool:
                    self.service_pool.save()

                self.service_pool.log(
                    f'Executed action {CALENDAR_ACTION_DICT.get(self.action, {}).get("description", self.action)} [{self.prettyParams}]',
                    level=log.LogLevel.INFO,
                )
            except Exception:
                self.service_pool.log(
                    f'Error executing scheduled action {CALENDAR_ACTION_DICT.get(self.action, {}).get("description", self.action)} [{self.prettyParams}]'
                )
                logger.exception('Error executing scheduled action')
        else:
            self.service_pool.log(f'Scheduled action not executed because is not supported: {self.action}')

        # On save, will regenerate nextExecution
        if save:
            self.save()

    def save(self, *args, **kwargs):
        lastExecution = self.last_execution or getSqlDatetime()
        possibleNext = calendar.CalendarChecker(self.calendar).nextEvent(
            checkFrom=lastExecution - self.offset, startEvent=self.at_start
        )
        if possibleNext:
            self.next_execution = possibleNext + self.offset
        else:
            self.next_execution = None

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f'Calendar of {self.service_pool.name},'
            f' last_execution = {self.last_execution},'
            f' next execution = {self.next_execution},'
            f' action = {self.action}, params = {self.params}'
        )
