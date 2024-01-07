# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
@author: Alexander Burmatov,  thatman at altlinux dot org
"""
import codecs
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy
from django.utils.translation import gettext_noop as _

from uds.core import exceptions, types, consts
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui

from .linux_osmanager import LinuxOsManager

if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module
    from uds.models.user_service import UserService


logger = logging.getLogger(__name__)


class LinuxOsADManager(LinuxOsManager):
    type_name = _('Linux OS Active Directory Manager')
    type_type = 'LinuxADManager'
    type_description = _('Os Manager to control Linux virtual machines with active directory')
    icon_file = 'losmanager.png'

    domain = gui.TextField(
        length=64,
        label=_('Domain'),
        order=1,
        tooltip=_('Domain to join machines to (use FQDN form, Netbios name not supported for most operations)'),
        required=True,
    )
    account = gui.TextField(
        length=64,
        label=_('Account'),
        order=2,
        tooltip=_('Account with rights to add machines to domain'),
        required=True,
    )
    password = gui.PasswordField(
        length=64,
        label=_('Password'),
        order=3,
        tooltip=_('Password of the account'),
        required=True,
    )
    ou = gui.TextField(
        length=256,
        label=_('OU'),
        order=4,
        tooltip=_(
            'Organizational unit where to add machines in domain (check it before using it). i.e.: ou=My Machines,dc=mydomain,dc=local'
        ),
    )
    clientSoftware = gui.ChoiceField(
        label=_('Client software'),
        order=5,
        tooltip=_('Use specific client software'),
        choices=[
            {'id': 'automatically', 'text': gettext_lazy('Automatically')},
            {'id': 'sssd', 'text': gettext_lazy('SSSD')},
            {'id': 'winbind', 'text': gettext_lazy('Winbind')},
        ],
        tab=types.ui.Tab.ADVANCED,
        default='automatically',
    )
    membershipSoftware = gui.ChoiceField(
        label=_('Membership software'),
        order=6,
        tooltip=_('Use specific membership software'),
        choices=[
            {'id': 'automatically', 'text': gettext_lazy('Automatically')},
            {'id': 'samba', 'text': gettext_lazy('Samba')},
            {'id': 'adcli', 'text': gettext_lazy('adcli')},
        ],
        tab=types.ui.Tab.ADVANCED,
        default='automatically',
    )
    removeOnExit = gui.CheckBoxField(
        label=_('Machine clean'),
        order=7,
        tooltip=_(
            'If checked, UDS will try to remove the machine from the domain USING the provided credentials'
        ),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )
    ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=8,
        tooltip=_('If checked, a ssl connection to Active Directory will be used'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )
    automaticIdMapping = gui.CheckBoxField(
        label=_('Automatic ID mapping'),
        order=9,
        tooltip=_('If checked, automatic ID mapping'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )

    # Inherits base "onLogout"
    onLogout = LinuxOsManager.onLogout
    idle = LinuxOsManager.idle
    deadLine = LinuxOsManager.deadLine

    _domain: str
    _ou: str
    _account: str
    _password: str
    _removeOnExit: str
    _ssl: str
    _automaticIdMapping: str
    _clientSoftware: str
    _serverSoftware: str
    _membershipSoftware: str

    def __init__(self, environment: 'Environment', values: 'Module.ValuesType') -> None:
        super().__init__(environment, values)
        if values:
            if values['domain'] == '':
                raise exceptions.validation.ValidationError(_('Must provide a domain!'))
            if values['account'] == '':
                raise exceptions.validation.ValidationError(_('Must provide an account to add machines to domain!'))
            if values['password'] == '':
                raise exceptions.validation.ValidationError(_('Must provide a password for the account!'))
            self._domain = values['domain']
            self._account = values['account']
            self._password = values['password']
            self._ou = values['ou'].strip()
            self._clientSoftware = values['clientSoftware']
            self._serverSoftware = 'active-directory'
            self._membershipSoftware = values['membershipSoftware']
            self._removeOnExit = 'y' if values['removeOnExit'] else 'n'
            self._ssl = 'y' if values['ssl'] else 'n'
            self._automaticIdMapping = 'y' if values['automaticIdMapping'] else 'n'
        else:
            self._domain = ''
            self._account = ''
            self._password = ''  # nosec: no encoded password
            self._ou = ''
            self._clientSoftware = ''
            self._serverSoftware = 'active-directory'
            self._membershipSoftware = ''
            self._removeOnExit = 'n'
            self._ssl = 'n'
            self._automaticIdMapping = 'n'

    def actorData(self, userService: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename_ad',
            'name': userService.getName(),
            'custom': {
                'domain': self._domain,
                'username': self._account,
                'password': self._password,
                'ou': self._ou,
                'isPersistent': self.isPersistent(),
                'clientSoftware': self._clientSoftware,
                'serverSoftware': self._serverSoftware,
                'membershipSoftware': self._membershipSoftware,
                'ssl': self._ssl == 'y',
                'automaticIdMapping': self._automaticIdMapping == 'y',
            }
        }

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        base = super().marshal()
        return '\t'.join(
            [
                'v1',
                self._domain,
                self._account,
                CryptoManager().encrypt(self._password),
                self._ou,
                self._clientSoftware,
                self._serverSoftware,
                self._membershipSoftware,
                self._removeOnExit,
                self._ssl,
                self._automaticIdMapping,
                codecs.encode(base, 'hex').decode(),
            ]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        values = data.decode('utf8').split('\t')
        if values[0] in ('v1'):
            self._domain = values[1]
            self._account = values[2]
            self._password = CryptoManager().decrypt(values[3])
            self._ou = values[4]
            self._clientSoftware = values[5]
            self._serverSoftware = values[6]
            self._membershipSoftware = values[7]
            self._removeOnExit = values[8]
            self._ssl = values[9]
            self._automaticIdMapping = values[10]
        super().unmarshal(codecs.decode(values[11].encode(), 'hex'))

    def valuesDict(self) -> gui.ValuesDictType:
        dct = super().valuesDict()
        dct['domain'] = self._domain
        dct['account'] = self._account
        dct['password'] = self._password
        dct['ou'] = self._ou
        dct['clientSoftware'] = self._clientSoftware
        dct['serverSoftware'] = self._serverSoftware
        dct['membershipSoftware'] = self._membershipSoftware
        dct['removeOnExit'] = self._removeOnExit == 'y'
        dct['ssl'] = self._ssl == 'y'
        dct['automaticIdMapping'] = self._automaticIdMapping == 'y'
        return dct
