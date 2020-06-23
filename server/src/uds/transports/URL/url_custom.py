# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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

from django.utils.translation import ugettext_noop as _
from django.urls import reverse
from django.http import HttpResponseRedirect

from uds.core.ui import gui

from uds.core import transports

from uds.core.util import os_detector as OsDetector
from uds.core.managers import cryptoManager
from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

logger = logging.getLogger(__name__)


class URLCustomTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    typeName = _('URL Launcher')
    typeType = 'URLTransport'
    typeDescription = _('Launchs an external UDS customized URL')
    iconFile = 'url.png'

    ownLink = True
    supportedOss = OsDetector.allOss
    protocol = transports.protocols.OTHER
    group = transports.DIRECT_GROUP

    urlPattern = gui.TextField(label=_('URL Pattern'), order=1, tooltip=_('URL Pattern to open (i.e. https://_IP_/test?user=_USER_'), defvalue='https://www.udsenterprise.com', length=64, required=True)

    forceNewWindow = gui.CheckBoxField(
        label=_('Force new HTML Window'),
        order=91,
        tooltip=_('If checked, every connection will try to open its own window instead of reusing the "global" one.'),
        defvalue=gui.FALSE,
        tab=gui.ADVANCED_TAB
    )

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces
        if not (self.urlPattern.value.startswith('http://') or self.urlPattern.value.startswith('https://')):
            raise transports.Transport.ValidationException(_('The url must be http or https'))

    # Same check as normal RDP transport
    def isAvailableFor(self, userService: 'models.UserService', ip: str) -> bool:
        # No check is done for URL transport
        return True

    def getLink(  # pylint: disable=too-many-locals
            self,
            userService: 'models.UserService',
            transport: 'models.Transport',
            ip: str,
            os: typing.Dict[str, str],
            user: 'models.User',
            password: str,
            request: 'HttpRequest'
        ) -> str:

        # Fix username/password acording to os manager
        username: str = user.getUsernameForAuth()
        username, password = userService.processUserPassword(username, password)

        url = (
            self.urlPattern.value.replace('_IP_', ip)
                                 .replace('_USERNAME_', username)
        )

        return HttpResponseRedirect(
            "{}{}".format(
                url,
                '&o_n_w=0;' if self.forceNewWindow.isTrue() else ''
            )
        )
