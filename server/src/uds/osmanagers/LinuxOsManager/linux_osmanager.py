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
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_noop as _

from uds.core import osmanagers, types, consts
from uds.core.types.services import ServiceType as serviceTypes
from uds.core.ui import gui
from uds.core.util import fields, log
from uds.core.types.states import State
from uds.core.workers import initialize

if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module
    from uds.models.user_service import UserService

logger = logging.getLogger(__name__)


class LinuxOsManager(osmanagers.OSManager):
    type_name = _('Linux OS Manager')
    type_type = 'LinuxManager'
    type_description = _('Os Manager to control Linux virtual machines')
    icon_file = 'losmanager.png'

    servicesType = serviceTypes.VDI

    on_logout = fields.on_logout_field()

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        default=-1,
        readonly=False,
        order=11,
        tooltip=_(
            'Maximum idle time (in seconds) before session is automatically closed to the user (<= 0 means no max idle time).'
        ),
        required=True,
    )

    deadline = gui.CheckBoxField(
        label=_('Calendar logout'),
        order=90,
        tooltip=_('If checked, UDS will try to logout user when the calendar for his current access expires'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )

    def _flag_processes_unused_machines(self) -> None:
        self.handles_unused_userservices = fields.onlogout_field_is_removable(self.on_logout)

    def initialize(self, values: 'Module.ValuesType') -> None:
        self._flag_processes_unused_machines()

    def release(self, userservice: 'UserService') -> None:
        pass

    def ignore_deadline(self) -> bool:
        return not self.deadline.as_bool()


    def is_removable_on_logout(self, userservice: 'UserService') -> bool:
        """
        if a machine is removable on logout
        """
        if not userservice.in_use:
            if fields.onlogout_field_is_removable(self.on_logout) or(
                not userservice.is_publication_valid() and fields.onlogout_field_is_keep(self.on_logout)
            ):
                return True

        return False

    def get_name(self, service: 'UserService') -> str:
        """
        gets name from deployed
        """
        return service.get_name()

    def do_log(self, service: 'UserService', data, origin=log.LogSource.OSMANAGER) -> None:
        # Stores a log associated with this service
        try:
            msg, slevel = data.split('\t')
            try:
                level = log.LogLevel.from_str(slevel)
            except Exception:
                logger.debug('Do not understand level %s', slevel)
                level = log.LogLevel.INFO
            log.log(service, level, msg, origin)
        except Exception:
            log.log(service, log.LogLevel.ERROR, f'do not understand {data}', origin)

    def actor_data(self, userService: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {'action': 'rename', 'name': userService.get_name()}  # No custom data

    def handle_unused(self, userservice: 'UserService') -> None:
        """
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        """
        if self.is_removable_on_logout(userservice):
            log.log(
                userservice,
                log.LogLevel.INFO,
                'Unused user service for too long. Removing due to OS Manager parameters.',
                log.LogSource.OSMANAGER,
            )
            userservice.remove()

    def is_persistent(self) -> bool:
        return fields.onlogout_field_is_persistent(self.on_logout)

    def check_state(self, userService: 'UserService') -> str:
        logger.debug('Checking state for service %s', userService)
        return State.RUNNING

    def max_idle(self) -> typing.Optional[int]:
        if self.idle.as_int() <= 0:
            return None

        return self.idle.as_int()

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        values = data.decode('utf8').split('\t')
        self.idle.value = -1
        self.deadline.value = True
        if values[0] == 'v1':
            self.on_logout.value = values[1]
        elif values[0] == 'v2':
            self.on_logout.value, self.idle.value = values[1], int(values[2])
        elif values[0] == 'v3':
            self.on_logout.value, self.idle.value, self.deadline.value = (
                values[1],
                int(values[2]),
                gui.as_bool(values[3]),
            )

        self._flag_processes_unused_machines()
        # Flag that we need an upgrade (remarshal and save)
        self.mark_for_upgrade()
