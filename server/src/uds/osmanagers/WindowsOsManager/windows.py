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
from uds.core.util import log
from uds.core.types.states import State
from uds.models import TicketStore

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService

logger = logging.getLogger(__name__)


def scrambleMsg(msg: str) -> str:
    """
    Simple scrambler so password are not seen at source page
    """
    data = msg.encode('utf8')
    res = b''
    n = 0x32
    for c in data[::-1]:
        res += bytes([c ^ n])
        n = (n + c) & 0xFF
    return codecs.encode(res, 'hex').decode()


class WindowsOsManager(osmanagers.OSManager):
    type_name = _('Windows Basic OS Manager')
    type_type = 'WindowsManager'
    type_description = _('Os Manager to control windows machines without domain.')
    icon_file = 'wosmanager.png'
    servicesType = serviceTypes.VDI

    on_logout = gui.ChoiceField(
        label=_('Logout Action'),
        order=10,
        readonly=True,
        tooltip=_('What to do when user logs out from service'),
        choices=[
            {'id': 'keep', 'text': typing.cast(str, gettext_lazy('Keep service assigned'))},
            {'id': 'remove', 'text': typing.cast(str, gettext_lazy('Remove service'))},
            {
                'id': 'keep-always',
                'text': typing.cast(str, gettext_lazy('Keep service assigned even on new publication')),
            },
        ],
        default='keep',
    )

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
        tooltip=_(
            'If checked, UDS will try to logout user when the calendar for his current access expires'
        ),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )

    _on_logout: str
    _idle: int
    _deadline: bool

    @staticmethod
    def validateLen(length):
        try:
            length = int(length)
        except Exception:
            raise exceptions.validation.ValidationError(
                _('Length must be numeric!!')
            ) from None
        if length > 6 or length < 1:
            raise exceptions.validation.ValidationError(
                _('Length must be betwen 1 and 6')
            )
        return length

    def _set_handles_unused(self):
        self.handles_unused_userservices = self._on_logout == 'remove'

    def __init__(self, environment, values):
        super().__init__(environment, values)
        if values is not None:
            self._on_logout = values['on_logout']
            self._idle = int(values['idle'])
            self._deadline = gui.as_bool(values['deadline'])
        else:
            self._on_logout = ''
            self._idle = -1
            self._deadline = True

        self._set_handles_unused()

    def is_removable_on_logout(self, userService: 'UserService') -> bool:
        """
        Says if a machine is removable on logout
        """
        if not userService.in_use:
            if (self._on_logout == 'remove') or (
                not userService.check_publication_validity() and self._on_logout == 'keep'
            ):
                return True

        return False

    def release(self, userService: 'UserService') -> None:
        pass

    def ignore_deadline(self) -> bool:
        return not self._deadline

    def get_name(self, userService: 'UserService') -> str:
        return userService.get_name()

    def do_log(self, userService: 'UserService', data: str, origin=log.LogSource.OSMANAGER):
        # Stores a log associated with this service
        try:
            msg, levelStr = data.split('\t')
            try:
                level = log.LogLevel.from_str(levelStr)
            except Exception:
                logger.debug('Do not understand level %s', levelStr)
                level = log.LogLevel.INFO

            log.log(userService, level, msg, origin)
        except Exception:
            logger.exception('WindowsOs Manager message log: ')
            log.log(
                userService, log.LogLevel.ERROR, f'do not understand {data}', origin
            )

    def actor_data(
        self, userService: 'UserService'
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        return {'action': 'rename', 'name': userService.get_name()}  # No custom data

    def process_user_password(
        self, userService: 'UserService', username: str, password: str
    ) -> tuple[str, str]:
        if userService.properties.get('sso_available') == '1':
            # Generate a ticket, store it and return username with no password
            domain = ''
            if '@' in username:
                username, domain = username.split('@')
            elif '\\' in username:
                username, domain = username.split('\\')

            creds = {'username': username, 'password': password, 'domain': domain}
            ticket = TicketStore.create(
                creds,validity=300
            )  # , owner=SECURE_OWNER, secure=True)
            return ticket, ''

        return osmanagers.OSManager.process_user_password(
            self, userService, username, password
        )

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

    def is_persistent(self):
        return self._on_logout == 'keep-always'

    def check_state(self, userservice: 'UserService') -> str:
        # will alway return true, because the check is done by an actor callback
        logger.debug('Checking state for service %s', userservice)
        return State.RUNNING

    def max_idle(self):
        """
        On production environments, will return no idle for non removable machines
        """
        if (
            self._idle <= 0
        ):  # or (settings.DEBUG is False and self._on_logout != 'remove'):
            return None

        return self._idle

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        return '\t'.join(
            ['v3', self._on_logout, str(self._idle), gui.bool_as_str(self._deadline)]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        vals = data.decode('utf8').split('\t')
        self._idle = -1
        self._deadline = True
        try:
            if vals[0] == 'v1':
                self._on_logout = vals[1]
            elif vals[0] == 'v2':
                self._on_logout, self._idle = vals[1], int(vals[2])
            elif vals[0] == 'v3':
                self._on_logout, self._idle, self._deadline = (
                    vals[1],
                    int(vals[2]),
                    gui.as_bool(vals[3]),
                )
        except Exception:
            logger.exception(
                'Exception unmarshalling. Some values left as default ones'
            )

        self._set_handles_unused()

    def get_fields_as_dict(self) -> 'gui.ValuesDictType':
        return {
            'on_logout': self._on_logout,
            'idle': str(self._idle),
            'deadline': gui.bool_as_str(self._deadline),
        }
