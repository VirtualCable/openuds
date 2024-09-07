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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import codecs
import random
import string
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import types
from uds.core.ui import gui
from uds.core.managers.crypto import CryptoManager
from uds.core import exceptions
from uds.core.util import log

from .windows import WindowsOsManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService


logger = logging.getLogger(__name__)


class WinRandomPassManager(WindowsOsManager):
    type_name = _('Windows Random Password OS Manager')
    type_type = 'WinRandomPasswordManager'
    type_description = _('Os Manager to control windows machines, with user password set randomly.')
    icon_file = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    user_account = gui.TextField(
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

    # Inherits base "on_logout"
    on_logout = WindowsOsManager.on_logout
    idle = WindowsOsManager.idle
    dead_line = WindowsOsManager.deadline

    def initialize(self, values: 'types.core.ValuesType') -> None:
        if values:
            self.user_account.value = self.user_account.value.strip()

            if self.user_account.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide an user account!!!'))
            if self.password.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide a password for the account!!!'))

    def update_credentials(self, userservice: 'UserService', username: str, password: str) -> tuple[str, str]:
        if username == self.user_account.value.strip():
            password = userservice.recover_value('winOsRandomPass')

        return WindowsOsManager.update_credentials(self, userservice, username, password)

    def gen_random_password(self, userservice: 'UserService') -> str:
        rnd_password = userservice.recover_value('winOsRandomPass')
        if not rnd_password:
            # Generates a password that conforms to complexity
            rnd = random.SystemRandom()
            base = ''.join(
                rnd.choice(v) for v in (string.ascii_lowercase, string.ascii_uppercase, string.digits)
            ) + rnd.choice('.+-')
            rnd_password = ''.join(rnd.choice(string.ascii_letters + string.digits) for _ in range(12))
            pos = rnd.randrange(0, len(rnd_password))
            rnd_password = rnd_password[:pos] + base + rnd_password[pos:]
            userservice.store_value('winOsRandomPass', rnd_password)
            log.log(
                userservice,
                types.log.LogLevel.INFO,
                f'Password set to "{rnd_password}"',
                types.log.LogSource.OSMANAGER,
            )
        return rnd_password

    def actor_data(self, userservice: 'UserService') -> dict[str, typing.Any]:
        return {
            'action': 'rename',
            'name': userservice.get_name(),
            # Repeat data, to keep compat with old versions of Actor (the part outside "custom")
            # Will be removed in a couple of versions (maybe 6.0? :D), maybe before (But not before 5.0)
            'username': self.user_account.value.strip(),
            'password': self.password.as_str(),
            'new_password': self.gen_random_password(userservice),
            'custom': {
                'username': self.user_account.value.strip(),
                'password': self.password.as_str(),
                'new_password': self.gen_random_password(userservice),
            },
        }

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        values = data.decode('utf8').split('\t')
        if values[0] == 'v1':
            self.user_account.value = values[1]
            self.password.value = CryptoManager().decrypt(values[2])
            super().unmarshal(codecs.decode(values[3].encode(), 'hex'))

        self.mark_for_upgrade()  # Force upgrade to new format
