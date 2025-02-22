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
import random
import string
import codecs
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core.ui import gui
from uds.core import exceptions, types
from uds.core.util import log

from .linux_osmanager import LinuxOsManager

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models.user_service import UserService


class LinuxRandomPassManager(LinuxOsManager):
    type_name = _('Linux Random Password OS Manager')
    type_type = 'LinRandomPasswordManager'
    type_description = _('Os Manager to control linux machines, with user password set randomly.')
    icon_file = 'losmanager.png'

    # Apart form data from linux os manager, we need also domain and credentials
    user_account = gui.TextField(
        length=64,
        label=_('Account'),
        order=2,
        tooltip=_('User account to change password'),
        required=True,
    )

    # Inherits base "on_logout"
    on_logout = LinuxOsManager.on_logout
    idle = LinuxOsManager.idle
    deadline = LinuxOsManager.deadline

    def initialize(self, values: 'gui.ValuesType') -> None:
        if values is not None:
            if values['user_account'] == '':
                raise exceptions.ui.ValidationError(_('Must provide an user account!!!'))

    def update_credentials(self, userservice: 'UserService', username: str, password: str) -> tuple[str, str]:
        if username == self.user_account.as_str():
            return (username, userservice.recover_value('linOsRandomPass'))
        return username, password

    def gen_random_password(self, service: 'UserService') -> str:
        random_password = service.recover_value('linOsRandomPass')
        if not random_password:
            random_password = ''.join(
                random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(16)
            )
            service.store_value('linOsRandomPass', random_password)
            log.log(
                service,
                types.log.LogLevel.INFO,
                f'Password set to "{random_password}"',
                types.log.LogSource.OSMANAGER,
            )

        return random_password

    def actor_data(self, userservice: 'UserService') -> types.osmanagers.ActorData:
        return types.osmanagers.ActorData(
            action='rename',
            name=userservice.get_name(),
            # Repeat data, to keep compat with old versions of Actor
            # Will be removed in a couple of versions
            compat=types.osmanagers.ActorData.Compat(
                username=self.user_account.as_str(),
                password='',  # On linux, user password is not needed so we provide an empty one
                new_password=self.gen_random_password(userservice),
            ),
            custom={
                'username': self.user_account.as_str(),
                'password': '',  # On linux, user password is not needed so we provide an empty one
                'new_password': self.gen_random_password(userservice),
            },
        )

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            super().unmarshal(data)
        else:
            values = data.split(b'\t')
            if values[0] == b'v1':
                self.user_account.value = values[1].decode()
                LinuxOsManager.unmarshal(self, codecs.decode(values[2], 'hex'))

            self.mark_for_upgrade()
