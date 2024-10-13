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
import collections.abc


from django.utils.translation import gettext_lazy as _
from django.db import models

from uds.core.util import calendar
from uds.core.managers.userservice import UserServiceManager
from uds.core import types, consts

from .calendar import Calendar
from .uuid_model import UUIDModel
from ..core.util.model import sql_now
from .service_pool import ServicePool
from .transport import Transport
from .authenticator import Authenticator

# from django.utils.translation import gettext_lazy as _, gettext


logger = logging.getLogger(__name__)


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

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_cal_action'
        app_label = 'uds'

    @property
    def offset(self) -> datetime.timedelta:
        return datetime.timedelta(minutes=self.events_offset)

    @property
    def pretty_params(self) -> str:
        try:
            cal_action = consts.calendar.CALENDAR_ACTION_DICT.get(self.action)

            if cal_action is None:
                raise Exception(f'Action {self.action} not found')

            params = json.loads(self.params)
            res: list[str] = []
            for param in cal_action['params']:
                val = params[param['name']]
                pretty_param = f'{param["name"]}='
                # Transport
                if param['type'] == 'transport':
                    try:
                        pretty_param += Transport.objects.get(uuid=val).name
                    except Exception:
                        pretty_param += '(invalid)'
                # Groups
                elif param['type'] == 'group':
                    try:
                        auth, grp = params[param['name']].split('@')
                        auth = Authenticator.objects.get(uuid=auth)
                        grp = auth.groups.get(uuid=grp)
                        pretty_param += grp.name + '@' + auth.name
                    except Exception:
                        pretty_param += '(invalid)'
                else:
                    pretty_param += str(val)
                res.append(pretty_param)
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
        if not self.service_pool.is_usable():
            logger.info(
                'Execution of task for %s due to contained state (restrained, in maintenance or removing)',
                self.service_pool.name,
            )
            return

        self.last_execution = sql_now()
        params = json.loads(self.params)

        should_save_servicepool = save

        def _numeric_value(field: str) -> int:
            v = int(params[field])
            return v if v >= 0 else 0

        # Actions related to calendar actions
        def _set_l1_cache() -> None:
            self.service_pool.cache_l1_srvs = _numeric_value('size')

        def _set_l2_cache() -> None:
            self.service_pool.cache_l2_srvs = _numeric_value('size')

        def _set_initial() -> None:
            self.service_pool.initial_srvs = _numeric_value('size')

        def _set_max() -> None:
            self.service_pool.max_srvs = _numeric_value('size')

        def _publish() -> None:
            nonlocal should_save_servicepool
            self.service_pool.publish()
            should_save_servicepool = False

        def _ignores_unused() -> None:
            self.service_pool.ignores_unused = params['state'] in ('true', '1', True)

        def _remove_userservices() -> None:
            # 1.- Remove usable assigned services (Ignore "creating ones", just for created)
            for userservice in self.service_pool.assigned_user_services().filter(
                state=types.states.State.USABLE
            ):
                userservice.release()

        def _remove_stuck_userservice() -> None:
            # 1.- Remove stuck assigned services (Ignore "creating ones", just for created)
            since = sql_now() - datetime.timedelta(hours=_numeric_value('hours'))
            for userservice in self.service_pool.assigned_user_services().filter(
                state_date__lt=since, state=types.states.State.USABLE
            ):
                userservice.release()

        def _del_all_transport() -> None:
            # 2.- Remove all transports
            self.service_pool.transports.clear()

        def _del_all_groups() -> None:
            # 3.- Remove all groups
            self.service_pool.assignedGroups.clear()

        def _clear_cache() -> None:
            # 4.- Remove all cache_l1_srvs
            for i in self.service_pool.cached_users_services().filter(
                UserServiceManager.manager().get_cache_state_filter(
                    self.service_pool,
                    (
                        types.services.CacheLevel.L1
                        if self.action == consts.calendar.CALENDAR_ACTION_CLEAN_CACHE_L1['id']
                        else types.services.CacheLevel.L2
                    ),
                )
            ):
                i.release()

        def _add_del_transport() -> None:
            try:
                t = Transport.objects.get(uuid=params['transport'])
                if self.action == consts.calendar.CALENDAR_ACTION_ADD_TRANSPORT['id']:
                    self.service_pool.transports.add(t)
                else:
                    self.service_pool.transports.remove(t)
            except Exception:
                self.service_pool.log(
                    'Scheduled action not executed because transport is not available anymore'
                )

        def _add_del_group() -> None:
            try:
                auth, grp = params['group'].split('@')
                grp = Authenticator.objects.get(uuid=auth).groups.get(uuid=grp)
                if self.action == consts.calendar.CALENDAR_ACTION_ADD_GROUP['id']:
                    self.service_pool.assignedGroups.add(grp)
                else:
                    self.service_pool.assignedGroups.remove(grp)
            except Exception:
                self.service_pool.log('Scheduled action not executed because group is not available anymore')
                
        def _set_display_custom_message() -> None:
            self.service_pool.display_custom_message = params['visible'] in ('true', '1', True)

        actions: collections.abc.Mapping[str, tuple[collections.abc.Callable[[], None], bool]] = {
            # Id, actions (lambda), saveServicePool (bool)
            consts.calendar.CALENDAR_ACTION_CACHE_L1['id']: (_set_l1_cache, True),
            consts.calendar.CALENDAR_ACTION_CACHE_L2['id']: (_set_l2_cache, True),
            consts.calendar.CALENDAR_ACTION_INITIAL['id']: (_set_initial, True),
            consts.calendar.CALENDAR_ACTION_MAX['id']: (_set_max, True),
            consts.calendar.CALENDAR_ACTION_PUBLISH['id']: (_publish, False),
            consts.calendar.CALENDAR_ACTION_IGNORE_UNUSED['id']: (_ignores_unused, True),
            consts.calendar.CALENDAR_ACTION_REMOVE_USERSERVICES['id']: (_remove_userservices, False),
            consts.calendar.CALENDAR_ACTION_REMOVE_STUCK_USERSERVICES['id']: (
                _remove_stuck_userservice,
                False,
            ),
            consts.calendar.CALENDAR_ACTION_DEL_ALL_TRANSPORTS['id']: (_del_all_transport, False),
            consts.calendar.CALENDAR_ACTION_DEL_ALL_GROUPS['id']: (_del_all_groups, False),
            consts.calendar.CALENDAR_ACTION_CLEAN_CACHE_L1['id']: (_clear_cache, False),
            consts.calendar.CALENDAR_ACTION_CLEAN_CACHE_L2['id']: (_clear_cache, False),
            consts.calendar.CALENDAR_ACTION_ADD_TRANSPORT['id']: (
                _add_del_transport,
                False,
            ),
            consts.calendar.CALENDAR_ACTION_DEL_TRANSPORT['id']: (
                _add_del_transport,
                False,
            ),
            consts.calendar.CALENDAR_ACTION_ADD_GROUP['id']: (_add_del_group, False),
            consts.calendar.CALENDAR_ACTION_DEL_GROUP['id']: (_add_del_group, False),
            consts.calendar.CALENDAR_ACTION_DISPLAY_CUSTOM_MESSAGE['id']: (_set_display_custom_message, True),
        }

        action_executor, should_save_servicepool = actions.get(self.action, (None, False))

        action = consts.calendar.CALENDAR_ACTION_DICT.get(self.action)
        description = self.action if not action else action.get('description', self.action)

        if action_executor:
            try:
                action_executor()

                if should_save_servicepool:
                    self.service_pool.save()

                self.service_pool.log(
                    f'Executed action {description} [{self.pretty_params}]',
                    level=types.log.LogLevel.INFO,
                )
            except Exception:
                self.service_pool.log(f'Error executing scheduled action {description} [{self.pretty_params}]')
                logger.exception('Error executing scheduled action')
        else:
            self.service_pool.log(f'Scheduled action not executed because is not supported: {self.action}')

        # On save, will regenerate next_execution
        if save:
            self.save()

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        last_execution = self.last_execution or sql_now()
        possible_next = calendar.CalendarChecker(self.calendar).next_event(
            check_from=last_execution - self.offset, start_event=self.at_start
        )
        if possible_next:
            self.next_execution = possible_next + self.offset
        else:
            self.next_execution = None

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f'Calendar of {self.service_pool.name},'
            f' last_execution = {self.last_execution},'
            f' next execution = {self.next_execution},'
            f' action = {self.action}, params = {self.params}'
        )
