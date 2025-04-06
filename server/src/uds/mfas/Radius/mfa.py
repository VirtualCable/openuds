# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Daniel Torregrosa
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import typing
import logging

from django.utils.translation import gettext_noop as _, gettext

from uds.core import mfas, exceptions, types
from uds.core.ui import gui

from uds.auths.Radius import client
from uds.auths.Radius.client import (
    # NOT_CHECKED,
    INCORRECT,
    CORRECT,
    NOT_NEEDED,
    # NEEDED
)
from uds.core.auths.auth import get_webpassword
from uds.core.util import fields

if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)


class RadiusOTP(mfas.MFA):
    '''
    Validates OTP challenge against a proper configured Radius Server with OTP
    using 'Access-Challenge' response from Radius Server [RFC2865, RFC5080]
    '''

    type_name = _('Radius OTP Challenge')
    type_type = 'RadiusOTP'
    type_description = _('Radius OTP Challenge')
    icon_file = 'radius.png'

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
    all_users_otp = gui.CheckBoxField(
        label=_('All users must send OTP'),
        order=4,
        default=True,
        tooltip=_(
            'If unchecked, an authentication step is needed in order to know if this user must enter OTP. '
            'If checked, all users must enter OTP, so authentication step is skipped.'
        ),
    )
    nas_identifier = gui.TextField(
        length=64,
        label=_('NAS Identifier'),
        default='uds-server',
        order=5,
        tooltip=_('NAS Identifier for Radius Server'),
        required=True,
        old_field_name='nasIdentifier',
    )

    login_without_mfa_policy = fields.login_without_mfa_policy_field()
    login_without_mfa_policy_networks = fields.login_without_mfa_policy_networks_field()
    allow_skip_mfa_from_networks = fields.allow_skip_mfa_from_networks_field()

    send_just_username = gui.CheckBoxField(
        label=_('Send only username (without domain) to radius server'),
        order=55,
        default=False,
        tooltip=_(
            'If unchecked, username will be sent as is to radius server. \n'
            'If checked, domain part will be removed from username before sending it to radius server.'
        ),
        required=False,
        tab=types.ui.Tab.CONFIG,
    )

    use_message_authenticator = gui.CheckBoxField(
        label=_('Use Message Authenticator'),
        default=False,
        order=13,
        tooltip=_('Use Message Authenticator for authentication'),
        tab=types.ui.Tab.CONFIG,
    )

    def radius_client(self) -> client.RadiusClient:
        """Return a new radius client ."""
        return client.RadiusClient(
            self.server.value,
            self.secret.value.encode(),
            auth_port=self.port.as_int(),
            nas_identifier=self.nas_identifier.value,
            use_message_authenticator=self.use_message_authenticator.as_bool(),
        )

    def check_result(self, action: str, request: 'ExtendedHttpRequest') -> mfas.MFA.RESULT:
        if mfas.LoginAllowed.check_action(action, request, self.login_without_mfa_policy_networks.value):
            return mfas.MFA.RESULT.OK
        raise Exception('User not allowed to login')

    def allow_login_without_identifier(self, request: 'ExtendedHttpRequest') -> typing.Optional[bool]:
        return None

    def label(self) -> str:
        return gettext('OTP Code')

    def html(self, request: 'ExtendedHttpRequest', userid: str, username: str) -> str:
        '''
        ToDo:
        - Maybe create a field in mfa definition to edit from admin panel ?
        - And/or add "Reply-Message" text from Radius Server response
        '''
        return gettext('Please enter OTP')

    def process(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        validity: typing.Optional[int] = None,
    ) -> 'mfas.MFA.RESULT':
        '''
        check if this user must send OTP
        in order to check this, it is neccesary to first validate password (again) with radius server
        and get also radius State value (otp session)
        '''
        if mfas.LoginAllowed.check_ip_allowed(request, self.login_without_mfa_policy_networks.value):
            return mfas.MFA.RESULT.ALLOWED

        # if we are in a "all-users-otp" policy, avoid this step and go directly to ask for OTP
        if self.all_users_otp.value:
            return mfas.MFA.RESULT.OK

        # The identifier has preference over username
        # MFA identifier will be normally be empty, unless the auhenticator provides it
        # I.E. The Radius Authenticator will provide the user that logged into the Radius Server
        username = identifier or username

        # Remove domain part from username if needed
        if self.send_just_username.value:
            username = username.strip().split('@')[0].split('\\')[-1]

        web_pwd = get_webpassword(request)
        try:
            connection = self.radius_client()
            auth_reply = connection.authenticate_challenge(username, password=web_pwd)
        except Exception as e:
            logger.error("Exception found connecting to Radius OTP %s: %s", e.__class__, e)
            if not mfas.LoginAllowed.check_action(
                self.login_without_mfa_policy.value, request, self.login_without_mfa_policy_networks.value
            ):
                raise Exception(_('Radius OTP connection error')) from e
            logger.warning(
                "Radius OTP connection error: Allowing access to user [%s] from IP [%s] without OTP",
                username,
                request.ip,
            )
            return mfas.MFA.RESULT.ALLOWED

        if auth_reply.pwd == INCORRECT:
            logger.warning(
                "Radius OTP error: User [%s] with invalid password from IP [%s]. Not synchronized password.",
                username,
                request.ip,
            )
            # we should not be here: not synchronized user password between auth server and radius server
            # What do we want to do here ??
            return self.check_result(self.login_without_mfa_policy.value, request)

        if auth_reply.otp_needed == NOT_NEEDED:
            logger.warning(
                "Radius OTP error: User [%s] without OTP data from IP [%s]",
                username,
                request.ip,
            )
            return self.check_result(self.login_without_mfa_policy.value, request)

        # Store state for later use, related to this user
        request.session[client.STATE_VAR_NAME] = auth_reply.state or b''

        # correct password and otp_needed
        return mfas.MFA.RESULT.OK

    def validate(
        self,
        request: 'ExtendedHttpRequest',
        userid: str,
        username: str,
        identifier: str,
        code: str,
        validity: typing.Optional[int] = None,
    ) -> None:
        '''
        Validate the OTP code

        we could have saved state+replyMessage in ddbb at "process" step and reuse it here
        but finally it is a lot easier to generate new one on each otp try
        otherwise we need to redirect to username/password form in each otp try in order to
        regenerate a new State after a wrong sent OTP code
        slightly less efficient but a lot simpler
        '''
        # The identifier has preference over username, but normally will be empty
        # This allows derived class to "alter" the username if needed
        username = identifier or username

        # Remove domain part from username if needed
        if self.send_just_username.value:
            username = username.strip().split('@')[0].split('\\')[-1]

        try:
            err = _('Invalid OTP code')

            web_pwd = get_webpassword(request)
            try:
                connection = self.radius_client()
                state = request.session.get(client.STATE_VAR_NAME, b'')
                if state:
                    # Remove state from session
                    del request.session[client.STATE_VAR_NAME]
                    # Use state to validate
                    auth_reply = connection.authenticate_challenge(username, otp=code, state=state)
                else:  # No state, so full authentication
                    auth_reply = connection.authenticate_challenge(username, password=web_pwd, otp=code)
            except Exception as e:
                logger.error("Exception found connecting to Radius OTP %s: %s", e.__class__, e)
                if mfas.LoginAllowed.check_action(
                    self.login_without_mfa_policy.value, request, self.login_without_mfa_policy_networks.value
                ):
                    raise Exception(_('Radius OTP connection error')) from e
                logger.warning(
                    "Radius OTP connection error: Allowing access to user [%s] from IP [%s] without OTP",
                    username,
                    request.ip,
                )
                return

            logger.debug("otp auth_reply: %s", auth_reply)
            if auth_reply.otp == CORRECT:
                logger.warning(
                    "Radius OTP correctly logged in: Allowing access to user [%s] from IP [%s] with correct OTP",
                    username,
                    request.ip,
                )
                return

        except Exception as e:
            # Any error means invalid code
            err = str(e)

        logger.warning(
            "Radius OTP error: Denying access to user [%s] from IP [%s] with incorrect OTP",
            username,
            request.ip,
        )
        raise exceptions.auth.MFAError(err)
