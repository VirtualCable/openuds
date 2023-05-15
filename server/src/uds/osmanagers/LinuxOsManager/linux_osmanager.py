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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _, gettext_lazy

from uds.core.services import types as serviceTypes
from uds.core.ui import gui
from uds.core import osmanagers
from uds.core.util.state import State
from uds.core.util import log

if typing.TYPE_CHECKING:
    from uds.models.user_service import UserService
    from uds.core.environment import Environment

logger = logging.getLogger(__name__)


class LinuxOsManager(osmanagers.OSManager):
    typeName = _('Linux OS Manager')
    typeType = 'LinuxManager'
    typeDescription = _('Os Manager to control Linux virtual machines')
    iconFile = 'losmanager.png'

    servicesType = (serviceTypes.VDI,)

    onLogout = gui.ChoiceField(
        label=_('Logout Action'),
        order=10,
        rdonly=True,
        tooltip=_('What to do when user logs out from service'),
        values=[
            {'id': 'keep', 'text': gettext_lazy('Keep service assigned')},
            {'id': 'remove', 'text': gettext_lazy('Remove service')},
            {
                'id': 'keep-always',
                'text': gettext_lazy('Keep service assigned even on new publication'),
            },
        ],
        defvalue='keep',
    )

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        defvalue=-1,
        rdonly=False,
        order=11,
        tooltip=_(
            'Maximum idle time (in seconds) before session is automatically closed to the user (<= 0 means no max idle time).'
        ),
        required=True,
    )

    deadLine = gui.CheckBoxField(
        label=_('Calendar logout'),
        order=90,
        tooltip=_(
            'If checked, UDS will try to logout user when the calendar for his current access expires'
        ),
        tab=gui.Tab.ADVANCED,
        defvalue=gui.TRUE,
    )

    def __setProcessUnusedMachines(self) -> None:
        self.processUnusedMachines = self._onLogout == 'remove'

    def __init__(self, environment, values) -> None:
        super().__init__(environment, values)
        if values is not None:
            self._onLogout = values['onLogout']
            self._idle = int(values['idle'])
            self._deadLine = gui.toBool(values['deadLine'])
        else:
            self._onLogout = ''
            self._idle = -1
            self._deadLine = True

        self.__setProcessUnusedMachines()

    def release(self, userService: 'UserService') -> None:
        pass

    def ignoreDeadLine(self) -> bool:
        return not self._deadLine

    def isRemovableOnLogout(self, userService: 'UserService') -> bool:
        '''
        Says if a machine is removable on logout
        '''
        if not userService.in_use:
            if (self._onLogout == 'remove') or (
                not userService.isValidPublication() and self._onLogout == 'keep'
            ):
                return True

        return False

    def getName(self, service: 'UserService') -> str:
        """
        gets name from deployed
        """
        return service.getName()

    def doLog(self, service: 'UserService', data, origin=log.LogSource.OSMANAGER) -> None:
        # Stores a log associated with this service
        try:
            msg, slevel = data.split('\t')
            try:
                level = log.LogLevel.fromStr(slevel)
            except Exception:
                logger.debug('Do not understand level %s', slevel)
                level = log.LogLevel.INFO
            log.doLog(service, level, msg, origin)
        except Exception:
            log.doLog(service, log.LogLevel.ERROR, f'do not understand {data}', origin)

    def actorData(
        self, userService: 'UserService'
    ) -> typing.MutableMapping[str, typing.Any]:
        return {'action': 'rename', 'name': userService.getName()}

    def processUnused(self, userService: 'UserService') -> None:
        """
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        """
        if self.isRemovableOnLogout(userService):
            log.doLog(
                userService,
                log.LogLevel.INFO,
                'Unused user service for too long. Removing due to OS Manager parameters.',
                log.LogSource.OSMANAGER,
            )
            userService.remove()

    def isPersistent(self) -> bool:
        return self._onLogout == 'keep-always'

    def checkState(self, userService: 'UserService') -> str:
        logger.debug('Checking state for service %s', userService)
        return State.RUNNING

    def maxIdle(self) -> typing.Optional[int]:
        """
        On production environments, will return no idle for non removable machines
        """
        if (
            self._idle <= 0
        ):  # or (settings.DEBUG is False and self._onLogout != 'remove'):
            return None

        return self._idle

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        return '\t'.join(
            ['v3', self._onLogout, str(self._idle), gui.fromBool(self._deadLine)]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        values = data.decode('utf8').split('\t')
        self._idle = -1
        self._deadLine = True
        if values[0] == 'v1':
            self._onLogout = values[1]
        elif values[0] == 'v2':
            self._onLogout, self._idle = values[1], int(values[2])
        elif values[0] == 'v3':
            self._onLogout, self._idle, self._deadLine = (
                values[1],
                int(values[2]),
                gui.toBool(values[3]),
            )

        self.__setProcessUnusedMachines()

    def valuesDict(self) -> gui.ValuesDictType:
        return {
            'onLogout': self._onLogout,
            'idle': str(self._idle),
            'deadLine': gui.fromBool(self._deadLine),
        }
