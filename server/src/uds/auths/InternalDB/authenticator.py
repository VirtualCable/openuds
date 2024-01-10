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

@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

import dns.resolver
import dns.reversename
from django.utils.translation import gettext_noop as _

from uds.core import auths, types, exceptions, consts
from uds.core.auths.auth import log_login
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui
from uds.core.util.state import State

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.types.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class InternalDBAuth(auths.Authenticator):
    type_name = _('Internal Database')
    type_type = 'InternalDBAuth'
    type_description = _(
        'Internal dabasase authenticator. Doesn\'t use external sources'
    )
    icon_file = 'auth.png'

    # If we need to enter the password for this user
    needs_password = True

    # This is the only internal source
    external_source = False

    differentForEachHost = gui.CheckBoxField(
        label=_('Different user for each host'),
        order=1,
        tooltip=_('If checked, each host will have a different user name'),
        default=False,
        readonly=True,
        tab=types.ui.Tab.ADVANCED,
    )
    reverseDns = gui.CheckBoxField(
        label=_('Reverse DNS'),
        order=2,
        tooltip=_('If checked, the host will be reversed dns'),
        default=False,
        readonly=True,
        tab=types.ui.Tab.ADVANCED,
    )
    acceptProxy = gui.CheckBoxField(
        label=_('Accept proxy'),
        order=3,
        default=False,
        tooltip=_(
            'If checked, requests via proxy will get FORWARDED ip address (take care with this bein checked, can take internal IP addresses from internet)'
        ),
        tab=types.ui.Tab.ADVANCED,
    )

    def getIp(self, request: 'ExtendedHttpRequest') -> str:
        ip = (
            request.ip_proxy if self.acceptProxy.as_bool() else request.ip
        )  # pylint: disable=maybe-no-member
        if self.reverseDns.as_bool():
            try:
                return str(
                    dns.resolver.query(dns.reversename.from_address(ip).to_text(), 'PTR')[0]
                )
            except Exception:  # nosec: intentionally
                pass
        return ip

    def mfa_identifier(self, username: str) -> str:
        try:
            self.db_obj().users.get(name=username.lower(), state=State.ACTIVE).mfa_data
        except Exception:  # nosec: This is e controled pickle loading
            pass
        return ''

    def transformed_username(self, username: str, request: 'ExtendedHttpRequest') -> str:
        username = username.lower()
        if self.differentForEachHost.as_bool():
            newUsername = (
                (request.ip_proxy if self.acceptProxy.as_bool() else request.ip)
                + '-'
                + username
            )
            # Duplicate basic user into username.
            auth = self.db_obj()
            # "Derived" users will belong to no group at all, because we will extract groups from "base" user
            # This way also, we protect from using forged "ip" + "username", because those will belong in fact to no group
            # and access will be denied
            try:
                usr = auth.users.get(name=username, state=State.ACTIVE)
                parent = usr.uuid
                usr.id = usr.uuid = None  # type: ignore  # Empty id
                if usr.real_name.strip() == '':
                    usr.real_name = usr.name
                usr.name = newUsername
                usr.parent = parent
                usr.save()
            except Exception:  # nosec: intentionally
                pass  # User already exists
            username = newUsername

        return username

    def authenticate(
        self,
        username: str,
        credentials: str,
        groupsManager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        username = username.lower()
        dbAuth = self.db_obj()
        try:
            user: 'models.User' = dbAuth.users.get(name=username, state=State.ACTIVE)
        except Exception:
            log_login(request, self.db_obj(), username, 'Invalid user')
            return types.auth.FAILED_AUTH

        if user.parent:  # Direct auth not allowed for "derived" users
            return types.auth.FAILED_AUTH

        # Internal Db Auth has its own groups. (That is, no external source). If a group is active it is valid
        if CryptoManager().check_hash(credentials, user.password):
            groupsManager.validate([g.name for g in user.groups.all()])
            return types.auth.SUCCESS_AUTH

        log_login(request, self.db_obj(), username, 'Invalid password')
        return types.auth.FAILED_AUTH

    def get_groups(self, username: str, groupsManager: 'auths.GroupsManager'):
        dbAuth = self.db_obj()
        try:
            user: 'models.User' = dbAuth.users.get(name=username.lower(), state=State.ACTIVE)
        except Exception:
            return

        groupsManager.validate([g.name for g in user.groups.all()])

    def get_real_name(self, username: str) -> str:
        # Return the real name of the user, if it is set
        try:
            user = self.db_obj().users.get(name=username.lower(), state=State.ACTIVE)
            return user.real_name or username
        except Exception:
            return super().get_real_name(username)

    def create_user(self, usrData):
        pass

    @staticmethod
    def test(env, data):  # pylint: disable=unused-argument
        return [True, _("Internal structures seems ok")]

    def check(self):
        return _("All seems fine in the authenticator.")

    def __str__(self):
        return "Internal DB Authenticator Authenticator"
