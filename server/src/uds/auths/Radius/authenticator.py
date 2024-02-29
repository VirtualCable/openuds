# -*- coding: utf-8 -*-

#
# Copyright (c) 2021 Virtual Cable S.L.U.
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
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import auths, environment, types
from uds.core.auths.auth import log_login
from uds.core.managers.crypto import CryptoManager
from uds.core.ui import gui

from . import client

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest
    
logger = logging.getLogger(__name__)


class RadiusAuth(auths.Authenticator):
    """
    UDS Radius authenticator
    """

    type_name = _('Radius Authenticator')
    type_type = 'RadiusAuthenticator'
    type_description = _('Radius Authenticator')
    icon_file = 'radius.png'

    label_username = _('User')
    label_groupname = _('Group')

    server = gui.TextField(
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('Radius Server IP or Hostname'),
        required=True,
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        default=1812,
        order=2,
        tooltip=_('Radius authentication port (usually 1812)'),
        required=True,
    )
    secret = gui.TextField(
        length=64,
        label=_('Secret'),
        order=3,
        tooltip=_('Radius client secret'),
        required=True,
    )

    nasIdentifier = gui.TextField(
        length=64,
        label=_('NAS Identifier'),
        default='uds-server',
        order=10,
        tooltip=_('NAS Identifier for Radius Server'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    appClassPrefix = gui.TextField(
        length=64,
        label=_('App Prefix for Class Attributes'),
        default='',
        order=11,
        tooltip=_('Application prefix for filtering groups from "Class" attribute'),
        tab=types.ui.Tab.ADVANCED,
    )

    globalGroup = gui.TextField(
        length=64,
        label=_('Global group'),
        default='',
        order=12,
        tooltip=_('If set, this value will be added as group for all radius users'),
        tab=types.ui.Tab.ADVANCED,
    )
    mfaAttr = gui.TextField(
        length=2048,
        lines=2,
        label=_('MFA attribute'),
        order=13,
        tooltip=_('Attribute from where to extract the MFA code'),
        required=False,
        tab=types.ui.Tab.MFA,
    )

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        pass

    def radius_client(self) -> client.RadiusClient:
        """Return a new radius client ."""
        return client.RadiusClient(
            self.server.value,
            self.secret.value.encode(),
            authPort=self.port.as_int(),
            nasIdentifier=self.nasIdentifier.value,
            appClassPrefix=self.appClassPrefix.value,
        )

    def mfa_storage_key(self, username: str) -> str:
        return 'mfa_' + str(self.db_obj().uuid) + username

    def mfa_identifier(self, username: str) -> str:
        return self.storage.get_unpickle(self.mfa_storage_key(username)) or ''

    def authenticate(
        self,
        username: str,
        credentials: str,
        groups_manager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        try:
            connection = self.radius_client()
            groups, mfaCode, state = connection.authenticate(
                username=username, password=credentials, mfaField=self.mfaAttr.value.strip()
            )
            # If state, store in session
            if state:
                request.session[client.STATE_VAR_NAME] = state.decode()
            # store the user mfa attribute if it is set
            if mfaCode:
                self.storage.put_pickle(
                    self.mfa_storage_key(username),
                    mfaCode,
                )

        except Exception:
            log_login(
                request,
                self.db_obj(),
                username,
                'Access denied by Raiuds',
            )
            return types.auth.FAILED_AUTH

        if self.globalGroup.value.strip():
            groups.append(self.globalGroup.value.strip())

        # Cache groups for "getGroups", because radius will not send us those
        with self.storage.as_dict() as storage:
            storage[username] = groups

        # Validate groups
        groups_manager.validate(groups)

        return types.auth.SUCCESS_AUTH

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        with self.storage.as_dict() as storage:
            groups_manager.validate(storage.get(username, []))

    def create_user(self, user_data: dict[str, str]) -> None:
        pass

    def remove_user(self, username: str) -> None:
        with self.storage.as_dict() as storage:
            if username in storage:
                del storage[username]
        return super().remove_user(username)

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        """Test the connection to the server ."""
        try:
            auth = RadiusAuth(None, env, data)  # type: ignore
            return auth.test_connection()
        except Exception as e:
            logger.error("Exception found testing Radius auth %s: %s", e.__class__, e)
            return types.core.TestResult(False, _('Error testing connection'))

    def test_connection(self) -> types.core.TestResult:
        """Test connection to Radius Server"""
        try:
            connection = self.radius_client()
            # Reply is not important...
            connection.authenticate(CryptoManager().random_string(10), CryptoManager().random_string(10))
        except client.RadiusAuthenticationError:
            pass
        except Exception:
            logger.exception('Connecting')
            return types.core.TestResult(False, _('Connection to Radius server failed'))
        return types.core.TestResult(True)
