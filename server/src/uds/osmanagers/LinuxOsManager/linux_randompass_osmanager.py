# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.U.
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
import random
import string
import codecs
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core.ui import gui
from uds.core import exceptions
from uds.core.util import log

from .linux_osmanager import LinuxOsManager

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models.user_service import UserService


class LinuxRandomPassManager(LinuxOsManager):
    typeName = _('Linux Random Password OS Manager')
    typeType = 'LinRandomPasswordManager'
    typeDescription = _(
        'Os Manager to control linux machines, with user password set randomly.'
    )
    iconFile = 'losmanager.png'

    # Apart form data from linux os manager, we need also domain and credentials
    userAccount = gui.TextField(
        length=64,
        label=_('Account'),
        order=2,
        tooltip=_('User account to change password'),
        required=True,
    )

    # Inherits base "onLogout"
    onLogout = LinuxOsManager.onLogout
    idle = LinuxOsManager.idle
    deadLine = LinuxOsManager.deadLine

    _userAccount: str

    def __init__(self, environment, values):
        super().__init__(environment, values)
        if values is not None:
            if values['userAccount'] == '':
                raise exceptions.ValidationError(
                    _('Must provide an user account!!!')
                )
            self._userAccount = values['userAccount']
        else:
            self._userAccount = ''

    def processUserPassword(
        self, userService: 'UserService', username: str, password: str
    ) -> typing.Tuple[str, str]:
        if username == self._userAccount:
            return (username, userService.recoverValue('linOsRandomPass'))
        return username, password

    def genPassword(self, service: 'UserService') -> str:
        randomPass = service.recoverValue('linOsRandomPass')
        if randomPass is None:
            randomPass = ''.join(
                random.SystemRandom().choice(string.ascii_letters + string.digits)
                for _ in range(16)
            )
            service.storeValue('linOsRandomPass', randomPass)
            log.doLog(
                service,
                log.LogLevel.INFO,
                f'Password set to "{randomPass}"',
                log.LogSource.OSMANAGER,
            )

        return randomPass

    def actorData(
        self, userService: 'UserService'
    ) -> typing.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename',
            'name': userService.getName(),
            'username': self._userAccount,
            'password': '',  # On linux, user password is not needed so we provide an empty one
            'new_password': self.genPassword(userService),
        }

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        base = LinuxOsManager.marshal(self)
        return '\t'.join(
            ['v1', self._userAccount, codecs.encode(base, 'hex').decode()]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        values = data.split(b'\t')
        if values[0] == b'v1':
            self._userAccount = values[1].decode()
            LinuxOsManager.unmarshal(self, codecs.decode(values[2], 'hex'))

    def valuesDict(self) -> gui.ValuesDictType:
        dic = LinuxOsManager.valuesDict(self)
        dic['userAccount'] = self._userAccount
        return dic
