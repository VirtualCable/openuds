import io
import logging
import typing

from pyrad.client import Client
from pyrad.dictionary import Dictionary
import pyrad.packet

__all__ = ['RadiusClient', 'RadiusAuthenticationError', 'RADDICT']

class RadiusAuthenticationError(Exception):
    pass

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
            server=server, authport=authPort, secret=secret, dict=Dictionary(io.StringIO(dictionary))
        )
        self.nasIdentifier = nasIdentifier
        self.appClassPrefix = appClassPrefix

    def authenticate(self, username: str, password: str) -> typing.List[str]:
        req: pyrad.packet.AuthPacket = self.radiusServer.CreateAuthPacket(
            code=pyrad.packet.AccessRequest,
            User_Name=username,
            NAS_Identifier=self.nasIdentifier,
        )

        req["User-Password"] = req.PwCrypt(password)

        reply = typing.cast(pyrad.packet.AuthPacket, self.radiusServer.SendPacket(req))

        if reply.code != pyrad.packet.AccessAccept:
            raise RadiusAuthenticationError('Access denied')

        # User accepted, extract groups...
        # All radius users belongs to, at least, 'uds-users' group
        groupClassPrefix = (self.appClassPrefix + 'group=').encode()
        groupClassPrefixLen = len(groupClassPrefix)
        if 'Class' in reply:
            groups = [i[groupClassPrefixLen:].decode() for i in typing.cast(typing.Iterable[bytes], reply['Class']) if i.startswith(groupClassPrefix)]
        else:
            logger.info('No "Class (25)" attribute found')
            return []

        return groups

