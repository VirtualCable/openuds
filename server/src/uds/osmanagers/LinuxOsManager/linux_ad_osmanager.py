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
from uds.core.module import Module
from uds.core.ui import gui
from uds.core.workers import initialize

from .linux_osmanager import LinuxOsManager

if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
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
            'Organizational unit where to add machines in domain (not used if IPA is selected). i.e.: ou=My Machines,dc=mydomain,dc=local'
        ),
    )
    client_software = gui.ChoiceField(
        label=_('Client software'),
        order=5,
        tooltip=_('Use specific client software'),
        choices=[
            gui.choice_item('automatically', gettext_lazy('Automatically')),
            gui.choice_item('sssd', gettext_lazy('SSSD')),
            gui.choice_item('winbind', gettext_lazy('Winbind')),
        ],
        tab=types.ui.Tab.ADVANCED,
        default='automatically',
    )
    membership_software = gui.ChoiceField(
        label=_('Membership software'),
        order=6,
        tooltip=_('Use specific membership software'),
        choices=[
            gui.choice_item('automatically', gettext_lazy('Automatically')),
            gui.choice_item('samba', gettext_lazy('Samba')),
            gui.choice_item('adcli', gettext_lazy('AdCli')),
        ],
        tab=types.ui.Tab.ADVANCED,
        default='automatically',
    )
    server_software = gui.ChoiceField(
        label=_('Server software'),
        order=7,
        tooltip=_('Use specific server software'),
        choices=[
            # gui.choice_item('automatically', gettext_lazy('Automatically')),
            gui.choice_item('active-directory', gettext_lazy('Active Directory')),
            gui.choice_item('freeipa', gettext_lazy('FreeIPA')),
        ],
        tab=types.ui.Tab.ADVANCED,
        default='active-directory',
    )
    remove_on_exit = gui.CheckBoxField(
        label=_('Machine clean'),
        order=7,
        tooltip=_(
            'If checked, UDS will try to remove the machine from the domain USING the provided credentials. (Not used if IPA is selected)'
        ),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )
    use_ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=8,
        tooltip=_('If checked, a ssl connection to Active Directory will be used'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )
    automatic_id_mapping = gui.CheckBoxField(
        label=_('Automatic ID mapping'),
        order=9,
        tooltip=_('If checked, automatic ID mapping'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )

    # Inherits base "on_logout"
    on_logout = LinuxOsManager.on_logout
    idle = LinuxOsManager.idle
    deadline = LinuxOsManager.deadline

    def initialize(self, values: 'Module.ValuesType') -> None:
        if values:
            if self.domain.value.strip() == '':
                raise exceptions.ui.ValidationError(_('Must provide a domain!'))
            if self.account.value.strip() == '':
                raise exceptions.ui.ValidationError(_('Must provide an account to add machines to domain!'))
            if self.password.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide a password for the account!'))
            self.ou.value = self.ou.value.strip()

    def actor_data(self, userservice: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename_ad',
            'name': userservice.get_name(),
            'custom': {
                'domain': self.domain.as_str(),
                'username': self.account.as_str(),
                'password': self.password.as_str(),
                'ou': self.ou.as_str(),
                'is_persistent': self.remove_on_exit.as_bool(),
                'client_software': self.client_software.as_str(),
                'server_software': self.server_software.as_str(),
                'membership_software': self.membership_software.as_str(),
                'ssl': self.use_ssl.as_bool(),
                'automatic_id_mapping': self.automatic_id_mapping.as_bool(),
            },
        }
