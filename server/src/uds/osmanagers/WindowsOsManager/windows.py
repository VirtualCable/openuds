# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2018 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import codecs
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_noop as _

from uds.core import exceptions, osmanagers, types, consts
from uds.core.types.services import ServiceType as serviceTypes
from uds.core.ui import gui
from uds.core.util import log, fields
from uds.core.types.states import State
from uds.models import TicketStore

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.models import UserService

logger = logging.getLogger(__name__)


class WindowsOsManager(osmanagers.OSManager):
    type_name = _('Windows Basic OS Manager')
    type_type = 'WindowsManager'
    type_description = _('Os Manager to control windows machines without domain.')
    icon_file = 'wosmanager.png'
    servicesType = serviceTypes.VDI

    on_logout = fields.on_logout_field()

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        default=-1,
        readonly=False,
        order=11,
        tooltip=_(
            'Maximum idle time (in seconds) before session is automatically closed to the user (<= 0 means no max. idle time)'
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

    def validate(self, values: 'types.core.ValuesType') -> None:
        self._flag_processes_unused_machines()

    def is_removable_on_logout(self, userservice: 'UserService') -> bool:
        """
        Says if a machine is removable on logout
        """
        if not userservice.in_use:
            if fields.onlogout_field_is_removable(self.on_logout) or (
                not userservice.is_publication_valid() and fields.onlogout_field_is_keep(self.on_logout)
            ):
                return True

        return False

    def release(self, userservice: 'UserService') -> None:
        pass

    def ignore_deadline(self) -> bool:
        return not self.deadline.as_bool()

    def get_name(self, userservice: 'UserService') -> str:
        return userservice.get_name()

    def actor_data(self, userservice: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {'action': 'rename', 'name': userservice.get_name()}  # No custom data

    def update_credentials(self, userservice: 'UserService', username: str, password: str) -> tuple[str, str]:
        if userservice.properties.get('sso_available') == '1':
            # Generate a ticket, store it and return username with no password
            domain = ''
            if '@' in username:
                username, domain = username.split('@')
            elif '\\' in username:
                username, domain = username.split('\\')

            creds = {'username': username, 'password': password, 'domain': domain}
            ticket = TicketStore.create(creds, validity=300)  # , owner=SECURE_OWNER, secure=True)
            return ticket, ''

        return super().update_credentials(userservice, username, password)

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

    def check_state(self, userservice: 'UserService') -> types.states.State:
        # will alway return true, because the check is done by an actor callback
        logger.debug('Checking state for service %s', userservice)
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
