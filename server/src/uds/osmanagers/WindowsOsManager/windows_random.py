# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
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
import codecs
import random
import string
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _
from uds.core.ui import gui
from uds.core.managers.crypto import CryptoManager
from uds.core import exceptions
from uds.core.util import log

from .windows import WindowsOsManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.environment import Environment
    from uds.models import UserService


logger = logging.getLogger(__name__)


class WinRandomPassManager(WindowsOsManager):
    type_name = _('Windows Random Password OS Manager')
    type_type = 'WinRandomPasswordManager'
    type_description = _('Os Manager to control windows machines, with user password set randomly.')
    icon_file = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    userAccount = gui.TextField(
        length=64,
        label=_('Account'),
        order=2,
        tooltip=_('User account to change password'),
        required=True,
    )
    password = gui.PasswordField(
        length=64,
        label=_('Password'),
        order=3,
        tooltip=_('Current (template) password of the user account'),
        required=True,
    )

    # Inherits base "onLogout"
    onLogout = WindowsOsManager.onLogout
    idle = WindowsOsManager.idle
    deadLine = WindowsOsManager.deadLine

    _user_account: str
    _password: str

    def __init__(self, environment: 'Environment', values: 'Module.ValuesType'):
        super().__init__(environment, values)
        if values:
            if values['userAccount'] == '':
                raise exceptions.validation.ValidationError(_('Must provide an user account!!!'))
            if values['password'] == '':
                raise exceptions.validation.ValidationError(_('Must provide a password for the account!!!'))
            self._user_account = values['userAccount']
            self._password = values['password']
        else:
            self._user_account = ''
            self._password = ''  # nosec: not a password (empty)

    def process_user_password(
        self, userService: 'UserService', username: str, password: str
    ) -> tuple[str, str]:
        if username == self._user_account:
            password = userService.recoverValue('winOsRandomPass')

        return WindowsOsManager.process_user_password(self, userService, username, password)

    def gen_random_password(self, userService: 'UserService'):
        randomPass = userService.recoverValue('winOsRandomPass')
        if not randomPass:
            # Generates a password that conforms to complexity
            rnd = random.SystemRandom()
            base = ''.join(
                rnd.choice(v) for v in (string.ascii_lowercase, string.ascii_uppercase, string.digits)
            ) + rnd.choice('.+-')
            randomPass = ''.join(rnd.choice(string.ascii_letters + string.digits) for _ in range(12))
            pos = rnd.randrange(0, len(randomPass))
            randomPass = randomPass[:pos] + base + randomPass[pos:]
            userService.storeValue('winOsRandomPass', randomPass)
            log.log(
                userService,
                log.LogLevel.INFO,
                f'Password set to "{randomPass}"',
                log.LogSource.OSMANAGER,
            )
        return randomPass

    def actor_data(self, userService: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename',
            'name': userService.get_name(),
            # Repeat data, to keep compat with old versions of Actor
            # Will be removed in a couple of versions
            'username': self._user_account,
            'password': self._password,
            'new_password': self.gen_random_password(userService),
            'custom': {
                'username': self._user_account,
                'password': self._password,
                'new_password': self.gen_random_password(userService),
            },
        }

    def marshal(self) -> bytes:
        '''
        Serializes the os manager data so we can store it in database
        '''
        base = codecs.encode(super().marshal(), 'hex').decode()
        return '\t'.join(['v1', self._user_account, CryptoManager().encrypt(self._password), base]).encode(
            'utf8'
        )

    def unmarshal(self, data: bytes) -> None:
        values = data.decode('utf8').split('\t')
        if values[0] == 'v1':
            self._user_account = values[1]
            self._password = CryptoManager().decrypt(values[2])
            super().unmarshal(codecs.decode(values[3].encode(), 'hex'))

    def get_dict_of_values(self) -> gui.ValuesDictType:
        dic = super().get_dict_of_values()
        dic['userAccount'] = self._user_account
        dic['password'] = self._password
        return dic
