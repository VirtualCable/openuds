# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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

from django.utils.translation import gettext_noop as _
from uds.core import auths
from uds.core.util import net
from uds.core.ui import gui

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest


class IPAuth(auths.Authenticator):
    acceptProxy = gui.CheckBoxField(
        label=_('Accept proxy'),
        default=gui.FALSE,
        order=50,
        tooltip=_(
            'If checked, requests via proxy will get FORWARDED ip address'
            ' (take care with this bein checked, can take internal IP addresses from internet)'
        ),
        tab=gui.Tab.ADVANCED,
    )

    visibleFromNets = gui.TextField(
        order=50,
        label=_('Visible only from this networks'),
        default='',
        tooltip=_(
            'This authenticator will be visible only from these networks. Leave empty to allow all networks'
        ),
        tab=gui.Tab.ADVANCED,
    )

    typeName = _('IP Authenticator')
    typeType = 'IPAuth'
    typeDescription = _('IP Authenticator')
    iconFile = 'auth.png'

    needsPassword = False
    userNameLabel = _('IP')
    groupNameLabel = _('IP Range')
    isExternalSource = True

    blockUserOnLoginFailures = False

    def getIp(self, request: 'ExtendedHttpRequest') -> str:
        ip = request.ip_proxy if self.acceptProxy.isTrue() else request.ip
        logger.debug('Client IP: %s', ip)
        # If ipv4 on ipv6, we must remove the ipv6 prefix
        if ':' in ip and '.' in ip:
            ip = ip.split(':')[-1]
        return ip

    def getGroups(self, username: str, groupsManager: 'auths.GroupsManager'):
        # these groups are a bit special. They are in fact ip-ranges, and we must check that the ip is in betwen
        # The ranges are stored in group names
        for g in groupsManager.getGroupsNames():
            try:
                if net.contains(g, username):
                    groupsManager.validate(g)
            except Exception as e:
                logger.error('Invalid network for IP auth: %s', e)

    def authenticate(
        self,
        username: str,
        credentials: str,  # pylint: disable=unused-argument
        groupsManager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
        # If credentials is a dict, that can't be sent directly from web interface, we allow entering
        if username == self.getIp(request):
            self.getGroups(username, groupsManager)
            return auths.SUCCESS_AUTH
        return auths.FAILED_AUTH

    def isAccesibleFrom(self, request: 'ExtendedHttpRequest'):
        """
        Used by the login interface to determine if the authenticator is visible on the login page.
        """
        validNets = self.visibleFromNets.value.strip()
        # If has networks and not in any of them, not visible
        if validNets and not net.contains(validNets, request.ip):
            return False
        return super().isAccesibleFrom(request)

    def internalAuthenticate(
        self,
        username: str,
        credentials: str,  # pylint: disable=unused-argument
        groupsManager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> auths.AuthenticationResult:
        # In fact, username does not matter, will get IP from request
        username = self.getIp(request)  # Override provided username and use source IP
        self.getGroups(username, groupsManager)
        if groupsManager.hasValidGroups() and self.dbAuthenticator().isValidUser(
            username, True
        ):
            return auths.SUCCESS_AUTH
        return auths.FAILED_AUTH

    @staticmethod
    def test(env, data):  # pylint: disable=unused-argument
        return [True, _("Internal structures seems ok")]

    def check(self):
        return _("All seems to be fine.")

    def getJavascript(self, request: 'ExtendedHttpRequest') -> typing.Optional[str]:
        # We will authenticate ip here, from request.ip
        # If valid, it will simply submit form with ip submited and a cached generated random password
        ip = self.getIp(request)
        gm = auths.GroupsManager(self.dbAuthenticator())
        self.getGroups(ip, gm)

        if gm.hasValidGroups() and self.dbAuthenticator().isValidUser(ip, True):
            return ('function setVal(element, value) {{\n'  # nosec: no user input, password is always EMPTY
                    '    document.getElementById(element).value = value;\n'
                    '}}\n'
                    f'setVal("id_user", "{ip}");\n'
                    'setVal("id_password", "");\n'
                    'document.getElementById("loginform").submit();\n')

        return 'alert("invalid authhenticator"); window.location.reload();'

    def __str__(self):
        return "IP Authenticator"
