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


class RadiusResult(typing.NamedTuple):
    """
    Result of an AccessChallenge request.
    """

    pwd: RadiusStates = RadiusStates.INCORRECT
    replyMessage: typing.Optional[bytes] = None
    state: typing.Optional[bytes] = None
    otp: RadiusStates = RadiusStates.NOT_CHECKED
    otp_needed: RadiusStates = RadiusStates.NOT_CHECKED


class RadiusClient:
    radiusServer: Client
    nasIdentifier: str
    appClassPrefix: str

    def __init__(
        self,
        server: str,
        secret: bytes,
        *,
        authPort: int = 1812,
        nasIdentifier: str = 'uds-server',
        appClassPrefix: str = '',
        dictionary: str = RADDICT,
    ) -> None:
        self.radiusServer = Client(
            server=server,
            authport=authPort,
            secret=secret,
            dict=Dictionary(io.StringIO(dictionary)),
        )
        self.nasIdentifier = nasIdentifier
        self.appClassPrefix = appClassPrefix

    def extractAccessChallenge(self, reply: pyrad.packet.AuthPacket) -> RadiusResult:
        return RadiusResult(
            pwd=RadiusStates.CORRECT,
            replyMessage=typing.cast(list[bytes], reply.get('Reply-Message') or [''])[0],
            state=typing.cast(list[bytes], reply.get('State') or [b''])[0],
            otp_needed=RadiusStates.NEEDED,
        )

    def sendAccessRequest(self, username: str, password: str, **kwargs) -> pyrad.packet.AuthPacket:
        req: pyrad.packet.AuthPacket = self.radiusServer.CreateAuthPacket(
            code=pyrad.packet.AccessRequest,
            User_Name=username,
            NAS_Identifier=self.nasIdentifier,
        )

        req["User-Password"] = req.PwCrypt(password)

        # Fill in extra fields
        for k, v in kwargs.items():
            req[k] = v

        return typing.cast(pyrad.packet.AuthPacket, self.radiusServer.SendPacket(req))

    # Second element of return value is the mfa code from field
    def authenticate(
        self, username: str, password: str, mfaField: str = ''
    ) -> typing.Tuple[list[str], str, bytes]:
        reply = self.sendAccessRequest(username, password)

        if reply.code not in (pyrad.packet.AccessAccept, pyrad.packet.AccessChallenge):
            raise RadiusAuthenticationError('Access denied')

        # User accepted, extract groups...
        # All radius users belongs to, at least, 'uds-users' group
        groupClassPrefix = (self.appClassPrefix + 'group=').encode()
        groupClassPrefixLen = len(groupClassPrefix)
        if 'Class' in reply:
            groups = [
                i[groupClassPrefixLen:].decode()
                for i in typing.cast(typing.Iterable[bytes], reply['Class'])
                if i.startswith(groupClassPrefix)
            ]
        else:
            logger.info('No "Class (25)" attribute found')
            return ([], '', b'')

        # ...and mfa code
        mfaCode = ''
        if mfaField and mfaField in reply:
            mfaCode = ''.join(
                i[groupClassPrefixLen:].decode()
                for i in typing.cast(typing.Iterable[bytes], reply['Class'])
                if i.startswith(groupClassPrefix)
            )
        return (groups, mfaCode, typing.cast(list[bytes], reply.get('State') or [b''])[0])

    def authenticate_only(self, username: str, password: str) -> RadiusResult:
        reply = self.sendAccessRequest(username, password)

        if reply.code == pyrad.packet.AccessChallenge:
            return self.extractAccessChallenge(reply)

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

        reply = self.sendAccessRequest(username, otp, State=state)

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
        reply = self.sendAccessRequest(username, password)

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
