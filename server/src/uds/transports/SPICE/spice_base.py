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
from uds.core import transports, types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class BaseSpiceTransport(transports.Transport):
    """
    Provides access via SPICE to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """

    is_base = True

    icon_file = 'spice.png'
    protocol = types.transports.Protocol.SPICE

    force_empty_creds = gui.CheckBoxField(
        order=1,
        label=_('Empty credentials'),
        tooltip=_('If checked, the credentials used to connect will be emtpy'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='useEmptyCreds',
    )
    forced_username = gui.TextField(
        order=2,
        label=_('Username'),
        tooltip=_('If not empty, this username will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedName',
    )
    forced_password = gui.PasswordField(
        order=3,
        label=_('Password'),
        tooltip=_('If not empty, this password will be always used as credential'),
        tab=types.ui.Tab.CREDENTIALS,
        old_field_name='fixedPassword',
    )
    server_certificate = gui.TextField(
        order=4,
        length=4096,
        lines=4,
        label=_('Certificate'),
        tooltip=_(
            'Server certificate (public), can be found on your ovirt engine, probably at /etc/pki/ovirt-engine/certs/ca.der (Use the contents of this file).'
        ),
        required=False,
        old_field_name='serverCertificate',
    )
    fullscreen = gui.CheckBoxField(
        order=5,
        label=_('Fullscreen Mode'),
        tooltip=_('If checked, viewer will be shown on fullscreen mode-'),
        tab=types.ui.Tab.ADVANCED,
        old_field_name='fullScreen',
    )
    allow_smartcards = gui.CheckBoxField(
        order=6,
        label=_('Smartcard Redirect'),
        tooltip=_('If checked, SPICE protocol will allow smartcard redirection.'),
        default=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='smartCardRedirect',
    )
    allow_usb_redirection = gui.CheckBoxField(
        order=7,
        label=_('Enable USB'),
        tooltip=_('If checked, USB redirection will be allowed.'),
        default=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='usbShare',
    )
    allow_usb_redirection_new_plugs = gui.CheckBoxField(
        order=8,
        label=_('New USB Auto Sharing'),
        tooltip=_('Auto-redirect USB devices when plugged in.'),
        default=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='autoNewUsbShare',
    )
    ssl_connection = gui.CheckBoxField(
        order=9,
        label=_('SSL Connection'),
        tooltip=_('If checked, SPICE protocol will allow SSL connections.'),
        default=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='SSLConnection',
    )

    overrided_proxy = gui.TextField(
        order=10,
        label=_('Override Proxy'),
        tooltip=_(
            'If not empty, this proxy will be used to connect to the service instead of the one provided by the hypervisor. Format: http://host:port'
        ),
        required=False,
        tab=types.ui.Tab.ADVANCED,
        pattern=types.ui.FieldPatternType.URL,
        old_field_name='overridedProxy',
    )

    def is_ip_allowed(self, userservice: 'models.UserService', ip: str) -> bool:
        """
        Checks if the transport is available for the requested destination ip
        """
        ready = self.cache.get(ip)
        if ready is None:
            userservice_instance = userservice.get_instance()
            con = userservice_instance.get_console_connection()

            logger.debug('Connection data: %s', con)

            if con is None:
                return False

            if con.proxy:  # if proxy is set, we can't use it
                return True

            # test ANY of the ports
            port_to_test = con.port if con.port != -1 else con.secure_port
            if port_to_test == -1:
                self.cache.put(
                    'cached_message', 'Could not find the PORT for connection', 120
                )  # Write a message, that will be used from getCustom
                logger.info('SPICE didn\'t find has any port: %s', con)
                return False

            self.cache.put(
                'cached_message',
                'Could not reach server "{}" on port "{}" from broker (prob. causes are name resolution & firewall rules)'.format(
                    con.address, port_to_test
                ),
                120,
            )

            if self.test_connectivity(userservice, con.address, port_to_test) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                ready = 'Y'

        return ready == 'Y'

    def get_available_error_msg(self, userservice: 'models.UserService', ip: str) -> str:
        msg = self.cache.get('cached_message')
        if msg is None:
            return transports.Transport.get_available_error_msg(self, userservice, ip)
        return msg

    def processed_username(self, userservice: 'models.UserService', user: 'models.User') -> str:
        v = self.process_user_password(userservice, user, '')
        return v.username

    def process_user_password(
        self,
        userservice: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
    ) -> types.connections.ConnectionData:
        username = user.get_username_for_auth()

        if self.forced_username.value:
            username = self.forced_username.value

        if self.forced_password.value:
            password = self.forced_password.value

        if self.force_empty_creds.as_bool():
            username, password = '', ''

        # Fix username/password acording to os manager
        username, password = userservice.process_user_password(username, password)

        return types.connections.ConnectionData(
            protocol=self.protocol,
            username=username,
            service_type=types.services.ServiceType.VDI,
            password=password,
        )

    def get_connection_info(
        self,
        userservice: typing.Union['models.UserService', 'models.ServicePool'],
        user: 'models.User',
        password: str,
    ) -> types.connections.ConnectionData:
        return self.process_user_password(userservice, user, password)
