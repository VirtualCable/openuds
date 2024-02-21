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
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import auths, types, consts
from uds.core.ui import gui
from uds.core.util import net

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core import environment


class IPAuth(auths.Authenticator):
    acceptProxy = gui.CheckBoxField(
        label=_('Accept proxy'),
        default=False,
        order=50,
        tooltip=_(
            'If checked, requests via proxy will get FORWARDED ip address'
            ' (take care with this bein checked, can take internal IP addresses from internet)'
        ),
        tab=types.ui.Tab.ADVANCED,
    )

    visibleFromNets = gui.TextField(
        order=50,
        label=_('Visible only from this networks'),
        default='',
        tooltip=_(
            'This authenticator will be visible only from these networks. Leave empty to allow all networks'
        ),
        tab=types.ui.Tab.ADVANCED,
    )

    type_name = _('IP Authenticator')
    type_type = 'IPAuth'
    type_description = _('IP Authenticator')
    icon_file = 'auth.png'

    needs_password = False
    label_username = _('IP')
    label_groupname = _('IP Range')

    block_user_on_failures = False

    def getIp(self, request: 'types.requests.ExtendedHttpRequest') -> str:
        ip = request.ip_proxy if self.acceptProxy.as_bool() else request.ip
        logger.debug('Client IP: %s', ip)
        # If ipv4 on ipv6, we must remove the ipv6 prefix
        if ':' in ip and '.' in ip:
            ip = ip.split(':')[-1]
        return ip

    def get_groups(self, username: str, groupsManager: 'auths.GroupsManager') -> None:
        # these groups are a bit special. They are in fact ip-ranges, and we must check that the ip is in betwen
        # The ranges are stored in group names
        for g in groupsManager.enumerate_groups_name():
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
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        # If credentials is a dict, that can't be sent directly from web interface, we allow entering
        if username == self.getIp(request):
            self.get_groups(username, groupsManager)
            return types.auth.SUCCESS_AUTH
        return types.auth.FAILED_AUTH

    def is_ip_allowed(self, request: 'types.requests.ExtendedHttpRequest') -> bool:
        """
        Used by the login interface to determine if the authenticator is visible on the login page.
        """
        validNets = self.visibleFromNets.value.strip()
        # If has networks and not in any of them, not visible
        if validNets and not net.contains(validNets, request.ip):
            return False
        return super().is_ip_allowed(request)

    def internal_authenticate(
        self,
        username: str,
        credentials: str,  # pylint: disable=unused-argument
        groupsManager: 'auths.GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        # In fact, username does not matter, will get IP from request
        username = self.getIp(request)  # Override provided username and use source IP
        self.get_groups(username, groupsManager)
        if groupsManager.has_valid_groups() and self.db_obj().is_user_allowed(
            username, True
        ):
            return types.auth.SUCCESS_AUTH
        return types.auth.FAILED_AUTH

    @staticmethod
    def test(env: 'environment.Environment', data: dict[str, str]) -> list[typing.Any]:
        return [True, _("Internal structures seems ok")]

    def check(self) -> str:
        return _("All seems to be fine.")

    def get_javascript(self, request: 'types.requests.ExtendedHttpRequest') -> typing.Optional[str]:
        # We will authenticate ip here, from request.ip
        # If valid, it will simply submit form with ip submited and a cached generated random password
        ip = self.getIp(request)
        gm = auths.GroupsManager(self.db_obj())
        self.get_groups(ip, gm)

        if gm.has_valid_groups() and self.db_obj().is_user_allowed(ip, True):
            return ('function setVal(element, value) {{\n'  # nosec: no user input, password is always EMPTY
                    '    document.getElementById(element).value = value;\n'
                    '}}\n'
                    f'setVal("id_user", "{ip}");\n'
                    'setVal("id_password", "");\n'
                    'document.getElementById("loginform").submit();\n')

        return 'alert("invalid authhenticator"); window.location.reload();'

    def __str__(self) -> str:
        return "IP Authenticator"
