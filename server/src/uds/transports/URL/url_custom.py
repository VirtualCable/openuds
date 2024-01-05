# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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

from uds import models
from uds.core import exceptions, transports, types, consts
from uds.core.ui import gui

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.types.request import ExtendedHttpRequestWithUser

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
    supportedOss = consts.os.ALL_OS_LIST
    protocol = transports.protocols.OTHER
    group = transports.DIRECT_GROUP

    urlPattern = gui.TextField(
        label=_('URL Pattern'),
        order=1,
        tooltip=_('URL Pattern to open (i.e. https://_IP_/test?user=_USER_'),
        default='https://www.udsenterprise.com',
        length=256,
        required=True,
    )

    forceNewWindow = gui.CheckBoxField(
        label=_('Force new HTML Window'),
        order=91,
        tooltip=_(
            'If checked, every connection will try to open its own window instead of reusing the "global" one.'
        ),
        default=False,
        tab=types.ui.Tab.ADVANCED,
    )

    def initialize(self, values: 'Module.ValuesType'):
        if not values:
            return
        # Strip spaces
        if not (
            self.urlPattern.value.startswith('http://')
            or self.urlPattern.value.startswith('https://')
        ):
            raise exceptions.validation.ValidationError(
                _('The url must be http or https')
            )

    # Same check as normal RDP transport
    def isAvailableFor(self, userService: 'models.UserService', ip: str) -> bool:
        # No check is done for URL transport
        return True

    def getLink(
        self,
        userService: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:

        # Fix username/password acording to os manager
        username: str = user.getUsernameForAuth()
        username, password = userService.process_user_password(username, password)

        url = self.urlPattern.value.replace('_IP_', ip).replace('_USER_', username)

        onw = (
            '&o_n_w={}'.format(hash(transport.name))
            if self.forceNewWindow.isTrue()
            else ''
        )
        return str("{}{}".format(url, onw))
