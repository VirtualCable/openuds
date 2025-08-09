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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds import models
from uds.core import exceptions, transports, types, consts
from uds.core.ui import gui

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class URLCustomTransport(transports.Transport):
    """
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    type_name = _('URL Launcher')
    type_type = 'URLTransport'
    type_description = _('Launchs an external UDS customized URL')
    icon_file = 'url.png'

    own_link = True
    supported_oss = consts.os.ALL_OS_LIST
    PROTOCOL = types.transports.Protocol.OTHER
    group = types.transports.Grouping.DIRECT

    url_pattern = gui.TextField(
        label=_('URL Pattern'),
        order=1,
        tooltip=_('URL Pattern to open (i.e. https://_IP_/test?user=_USER_'),
        default='https://www.udsenterprise.com',
        length=256,
        required=True,
        old_field_name='urlPattern',  # Allows compat with old versions
    )

    force_new_window = gui.ChoiceField(
        order=91,
        label=_('Force new HTML Window'),
        tooltip=_('Select windows behavior for opening URL'),
        required=True,
        choices=[
            gui.choice_item(
                'false',
                _('Open every connection on the same window, but keeps UDS window.'),
            ),
            gui.choice_item('true', _('Force every connection to be opened on a new window.')),
            gui.choice_item(
                'overwrite',
                _('Override UDS window and replace it with the connection.'),
            ),
        ],
        default='true',
        tab=types.ui.Tab.ADVANCED,
        old_field_name='forceNewWindow',
    )

    def initialize(self, values: 'types.core.ValuesType') -> None:
        if not values:
            return
        # Strip spaces
        if not (self.url_pattern.value.startswith('http://') or self.url_pattern.value.startswith('https://')):
            raise exceptions.ui.ValidationError(_('The url must be http or https'))

    # Same check as normal RDP transport
    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        # No check is done for URL transport
        return True

    def get_link(
        self,
        userservice: 'models.UserService',
        transport: 'models.Transport',
        ip: str,
        os: 'types.os.DetectedOsInfo',
        user: 'models.User',
        password: str,
        request: 'ExtendedHttpRequestWithUser',
    ) -> str:

        # Fix username/password acording to os manager
        username: str = user.get_username_for_auth()
        username, password = userservice.process_user_password(username, password)

        return self.update_link_window(
            self.url_pattern.value.replace('_IP_', ip).replace('_USER_', username),
            on_same_window=self.force_new_window.value == 'overwrite',
            on_new_window=self.force_new_window.value == 'true',
            uuid=userservice.service_pool.uuid if self.force_new_window.value == 'true' else None,
            default_uuid=userservice.service_pool.uuid,
        )
