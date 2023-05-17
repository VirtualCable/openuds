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

from uds.core.ui import gui
from uds.core import auths
from uds.core.managers.crypto import CryptoManager
from uds.core.auths.auth import authLogLogin

from . import client

if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class RadiusAuth(auths.Authenticator):
    """
    UDS Radius authenticator
    """

    typeName = _('Radius Authenticator')
    typeType = 'RadiusAuthenticator'
    typeDescription = _('Radius Authenticator')
    iconFile = 'radius.png'

    userNameLabel = _('User')
    groupNameLabel = _('Group')

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
        defvalue='1812',
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
        defvalue='uds-server',
        order=10,
        tooltip=_('NAS Identifier for Radius Server'),
        required=True,
        tab=gui.Tab.ADVANCED,
    )

    appClassPrefix = gui.TextField(
        length=64,
        label=_('App Prefix for Class Attributes'),
        defvalue='',
        order=11,
        tooltip=_('Application prefix for filtering groups from "Class" attribute'),
        tab=gui.Tab.ADVANCED,
    )

    globalGroup = gui.TextField(
        length=64,
        label=_('Global group'),
        defvalue='',
        order=12,
        tooltip=_('If set, this value will be added as group for all radius users'),
        tab=gui.Tab.ADVANCED,
    )
    mfaAttr = gui.TextField(
        length=2048,
        multiline=2,
        label=_('MFA attribute'),
        order=13,
        tooltip=_('Attribute from where to extract the MFA code'),
        required=False,
        tab=gui.Tab.MFA,
    )

    def initialize(self, values: typing.Optional[typing.Dict[str, typing.Any]]) -> None:
        pass

    def radiusClient(self) -> client.RadiusClient:
        """Return a new radius client ."""
        return client.RadiusClient(
            self.server.value,
            self.secret.value.encode(),
            authPort=self.port.num(),
            nasIdentifier=self.nasIdentifier.value,
            appClassPrefix=self.appClassPrefix.value,
        )

    def mfaStorageKey(self, username: str) -> str:
        return 'mfa_' + str(self.dbAuthenticator().uuid) + username

    def mfaIdentifier(self, username: str) -> str:
        return self.storage.getPickle(self.mfaStorageKey(username)) or ''

    def authenticate(
        self,
        username: str,
        credentials: str,
        groupsManager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
        try:
            connection = self.radiusClient()
            groups, mfaCode = connection.authenticate(username=username, password=credentials, mfaField=self.mfaAttr.value.strip())
            # store the user mfa attribute if it is set
            if mfaCode:
                self.storage.putPickle(
                    self.mfaStorageKey(username),
                    mfaCode,
                )

        except Exception:
            authLogLogin(
                request,
                self.dbAuthenticator(),
                username,
                'Access denied by Raiuds',
            )
            return auths.FAILED_AUTH

        if self.globalGroup.value.strip():
            groups.append(self.globalGroup.value.strip())

        # Cache groups for "getGroups", because radius will not send us those
        with self.storage.map() as storage:
            storage[username] = groups

        # Validate groups
        groupsManager.validate(groups)

        return auths.SUCCESS_AUTH

    def getGroups(self, username: str, groupsManager: 'auths.GroupsManager') -> None:
        with self.storage.map() as storage:
            groupsManager.validate(storage.get(username, []))

    def createUser(self, usrData: typing.Dict[str, str]) -> None:
        pass

    def removeUser(self, username: str) -> None:
        with self.storage.map() as storage:
            if username in storage:
                del storage[username]
        return super().removeUser(username)

    @staticmethod
    def test(env, data):
        """Test the connection to the server ."""
        try:
            auth = RadiusAuth(None, env, data)  # type: ignore
            return auth.testConnection()
        except Exception as e:
            logger.error("Exception found testing Radius auth %s: %s", e.__class__, e)
            return [False, _('Error testing connection')]

    def testConnection(self):
        """Test connection to Radius Server"""
        try:
            connection = self.radiusClient()
            # Reply is not important...
            connection.authenticate(
                CryptoManager().randomString(10), CryptoManager().randomString(10)
            )
        except client.RadiusAuthenticationError:
            pass
        except Exception:
            logger.exception('Connecting')
            return [False, _('Connection to Radius server failed')]
        return [True, _('Connection to Radius server seems ok')]
