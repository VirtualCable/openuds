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
# pyright: reportUnknownMemberType=false
import dataclasses
import io
import logging
import enum
import typing
import collections.abc
import string

from pyrad.client import Client
from pyrad.dictionary import Dictionary
import pyrad.packet

logger = logging.getLogger(__name__)

RADDICT = """ATTRIBUTE   User-Name       1   string
ATTRIBUTE   User-Password       2   string
ATTRIBUTE   CHAP-Password       3   octets
ATTRIBUTE   NAS-IP-Address      4   ipaddr
ATTRIBUTE   NAS-Port        5   integer
ATTRIBUTE   Service-Type        6   integer
ATTRIBUTE   Framed-Protocol     7   integer
ATTRIBUTE   Framed-IP-Address   8   ipaddr
ATTRIBUTE   Framed-IP-Netmask   9   ipaddr
ATTRIBUTE   Framed-Routing      10  integer
ATTRIBUTE   Filter-Id       11  string
ATTRIBUTE   Framed-MTU      12  integer
ATTRIBUTE   Framed-Compression  13  integer
ATTRIBUTE   Login-IP-Host       14  ipaddr
ATTRIBUTE   Login-Service       15  integer
ATTRIBUTE   Login-TCP-Port      16  integer
ATTRIBUTE   Reply-Message       18  string
ATTRIBUTE   Callback-Number     19  string
ATTRIBUTE   Callback-Id     20  string
ATTRIBUTE   Framed-Route        22  string
ATTRIBUTE   Framed-IPX-Network  23  ipaddr
ATTRIBUTE   State           24  octets
ATTRIBUTE   Class           25  octets
ATTRIBUTE   Vendor-Specific     26  octets
ATTRIBUTE   Session-Timeout     27  integer
ATTRIBUTE   Idle-Timeout        28  integer
ATTRIBUTE   Termination-Action  29  integer
ATTRIBUTE   Called-Station-Id   30  string
ATTRIBUTE   Calling-Station-Id  31  string
ATTRIBUTE   NAS-Identifier      32  string
ATTRIBUTE   Proxy-State     33  octets
ATTRIBUTE   Login-LAT-Service   34  string
ATTRIBUTE   Login-LAT-Node      35  string
ATTRIBUTE   Login-LAT-Group     36  octets
ATTRIBUTE   Framed-AppleTalk-Link   37  integer
ATTRIBUTE   Framed-AppleTalk-Network 38 integer
ATTRIBUTE   Framed-AppleTalk-Zone   39  string"""

# For AccessChallenge return values
NOT_CHECKED, INCORRECT, CORRECT = -1, 0, 1  # for pwd and otp
NOT_NEEDED, NEEDED = INCORRECT, CORRECT  # for otp_needed

STATE_VAR_NAME = 'radius_state'


class RadiusAuthenticationError(Exception):
    pass


class RadiusStates(enum.IntEnum):
    NOT_CHECKED = -1
    INCORRECT = 0
    CORRECT = 1

    # Aliases
    NOT_NEEDED = INCORRECT
    NEEDED = CORRECT

@dataclasses.dataclass
class RadiusResult:
    """
    Result of an AccessChallenge request.
    """

    pwd: RadiusStates = RadiusStates.INCORRECT
    reply_message: typing.Optional[bytes] = None
    state: typing.Optional[bytes] = None
    otp: RadiusStates = RadiusStates.NOT_CHECKED
    otp_needed: RadiusStates = RadiusStates.NOT_CHECKED


class RadiusClient:
    server: Client
    nas_identifier: str
    appclass_prefix: str
    use_message_authenticator: bool

    def __init__(
        self,
        server: str,
        secret: bytes,
        *,
        auth_port: int = 1812,
        nas_identifier: str = 'uds-server',
        appclass_prefix: str = '',
        dictionary: str = RADDICT,
        use_message_authenticator: bool = False,
    ) -> None:
        self.server = Client(
            server=server,
            authport=auth_port,
            secret=secret,
            dict=Dictionary(io.StringIO(dictionary)),
        )
        self.nas_identifier = nas_identifier
        self.appclass_prefix = appclass_prefix
        self.use_message_authenticator = use_message_authenticator

    def extract_access_challenge(self, reply: pyrad.packet.AuthPacket) -> RadiusResult:
        return RadiusResult(
            pwd=RadiusStates.CORRECT,
            reply_message=typing.cast(list[bytes], reply.get('Reply-Message') or [''])[0],
            state=typing.cast(list[bytes], reply.get('State') or [b''])[0],
            otp_needed=RadiusStates.NEEDED,
        )
        
    def send_access_request(self, username: str, password: str, **kwargs: typing.Any) -> pyrad.packet.AuthPacket:
        req: pyrad.packet.AuthPacket = self.server.CreateAuthPacket(
            code=pyrad.packet.AccessRequest,
            User_Name=username,
            NAS_Identifier=self.nas_identifier,
        )

        req["User-Password"] = req.PwCrypt(password)
        
        if self.use_message_authenticator:
            req.add_message_authenticator()

        # Fill in extra fields
        for k, v in kwargs.items():
            req[k] = v

        return typing.cast(pyrad.packet.AuthPacket, self.server.SendPacket(req))

    # Second element of return value is the mfa code from field
    def authenticate(
        self, username: str, password: str, mfa_field: str = ''
    ) -> tuple[list[str], str, bytes]:
        reply = self.send_access_request(username, password)

        if reply.code not in (pyrad.packet.AccessAccept, pyrad.packet.AccessChallenge):
            raise RadiusAuthenticationError('Access denied')

        # User accepted, extract groups...
        # All radius users belongs to, at least, 'uds-users' group
        groupclass_prefix = (self.appclass_prefix + 'group=').encode()
        groupclass_prefix_len = len(groupclass_prefix)
        if 'Class' in reply:
            groups = [
                i[groupclass_prefix_len:].decode()
                for i in typing.cast(collections.abc.Iterable[bytes], reply['Class'])
                if i.startswith(groupclass_prefix)
            ]
        else:
            logger.info('No "Class (25)" attribute found')
            return ([], '', b'')

        # ...and mfa code
        mfa_code = ''
        if mfa_field and mfa_field in reply:
            mfa_code = ''.join(
                i[groupclass_prefix_len:].decode()
                for i in typing.cast(collections.abc.Iterable[bytes], reply['Class'])
                if i.startswith(groupclass_prefix)
            )
        return (groups, mfa_code, typing.cast(list[bytes], reply.get('State') or [b''])[0])

    def authenticate_only(self, username: str, password: str) -> RadiusResult:
        reply = self.send_access_request(username, password)

        if reply.code == pyrad.packet.AccessChallenge:
            return self.extract_access_challenge(reply)

        # user/pwd accepted: this user does not have challenge data
        if reply.code == pyrad.packet.AccessAccept:
            return RadiusResult(
                pwd=RadiusStates.CORRECT,
                otp_needed=RadiusStates.NOT_CHECKED,
            )

        # user/pwd rejected
        return RadiusResult(
            pwd=RadiusStates.INCORRECT,
            state=typing.cast(list[bytes], reply.get('State') or [b''])[0],
        )

    def challenge_only(self, username: str, otp: str, state: bytes = b'0000000000000000') -> RadiusResult:
        # clean otp code
        otp = ''.join([x for x in otp if x in string.digits])

        logger.debug('Sending AccessChallenge request wit otp [%s]', otp)

        reply = self.send_access_request(username, otp, State=state)

        logger.debug('Received AccessChallenge reply: %s', reply)

        # correct OTP challenge
        if reply.code == pyrad.packet.AccessAccept:
            return RadiusResult(
                otp=RadiusStates.CORRECT,
            )

        # incorrect OTP challenge
        return RadiusResult(
            otp=RadiusStates.INCORRECT,
            state=typing.cast(list[bytes], reply.get('State') or [b''])[0],
        )

    def authenticate_and_challenge(self, username: str, password: str, otp: str) -> RadiusResult:
        reply = self.send_access_request(username, password)

        if reply.code == pyrad.packet.AccessChallenge:
            state = typing.cast(list[bytes], reply.get('State') or [b''])[0]
            # replyMessage = typing.cast(list[bytes], reply.get('Reply-Message') or [''])[0]
            return self.challenge_only(username, otp, state=state)

        # user/pwd accepted: but this user does not have challenge data
        # we should not be here...
        if reply.code == pyrad.packet.AccessAccept:
            logger.warning("Radius OTP error: cheking for OTP for not needed user [%s]", username)
            return RadiusResult(
                pwd=RadiusStates.CORRECT,
                otp_needed=RadiusStates.NOT_NEEDED,
                state=typing.cast(list[bytes], reply.get('State') or [b''])[0],
            )

        # TODO: accept more AccessChallenge authentications (as RFC says)

        # incorrect user/pwd
        return RadiusResult()

    def authenticate_challenge(
        self, username: str, password: str = '', otp: str = '', state: typing.Optional[bytes] = None
    ) -> RadiusResult:
        '''
        wrapper for above 3 functions: authenticate_only, challenge_only, authenticate_and_challenge
        calls wrapped functions based on passed input values: (pwd/otp/state)
        '''
        # clean input data
        # Keep only numbers in otp
        state = state or b'0000000000000000'
        otp = ''.join([x for x in otp if x in string.digits])
        username = username.strip()
        password = password.strip()
        state = state.strip()

        if not username or (not password and not otp):
            return RadiusResult()  # no user/pwd provided

        if not otp:
            return self.authenticate_only(username, password)
        if otp and not password:
            # check only otp with static/invented state. allow this ?
            return self.challenge_only(username, otp, state=state)
        # otp and password
        return self.authenticate_and_challenge(username, password, otp)
