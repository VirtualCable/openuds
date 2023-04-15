# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.U.
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
import re
import socket
import logging
import typing
import ipaddress


class IpType(typing.NamedTuple):
    ip: int
    version: typing.Literal[4, 6, 0]  # 0 is only used for invalid detected ip


class NetworkType(typing.NamedTuple):
    start: int
    end: int
    version: typing.Literal[0, 4, 6]  # 4 or 6


logger = logging.getLogger(__name__)

# Test patters for networks IPv4
reCIDRIPv4 = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/([0-9]{1,2})$'
)
reMaskIPv4 = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})netmask([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
)
re1AsteriskIPv4 = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.\*$')
re2AsteriskIPv4 = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.\*\.?\*?$')
re3AsteriskIPv4 = re.compile(r'^([0-9]{1,3})\.\*\.?\*?\.?\*?$')
reRangeIPv4 = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})-([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
)
reSingleIPv4 = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$')


def ipToLong(ip: str) -> IpType:
    """
    Convert an ipv4 or ipv6 address to its long representation
    """
    # First, check if it's an ipv6 address
    try:
        if ':' in ip and '.' not in ip:
            return IpType(int(ipaddress.IPv6Address(ip)), 6)
        if ':' in ip and '.' in ip:
            ip = ip.split(':')[
                -1
            ]  # Last part of ipv6 address is ipv4 address (has dots and colons, so we can't use ipaddress)
        return IpType(int(ipaddress.IPv4Address(ip)), 4)
    except Exception as e:
        logger.error('Ivalid value: %s (%s)', ip, e)
        return IpType(0, 0)  # Invalid values will map to "0.0.0.0" --> 0


def longToIp(n: int, version: typing.Literal[0, 4, 6] = 0) -> str:
    """
    convert long int to ipv4 or ipv6 address, depending on size
    """
    if n > 2**32 or version == 6:
        return str(ipaddress.IPv6Address(n).compressed)
    return str(ipaddress.IPv4Address(n))


def networkFromStringIPv4(strNets: str) -> NetworkType:
    '''
    Parses the network from strings in this forms:
      - A.* (or A.*.* or A.*.*.*)
      - A.B.* (or A.B.*.* )
      - A.B.C.* (i.e. 192.168.0.*)
      - A.B.C.D/N (i.e. 192.168.0.0/24)
      - A.B.C.D netmask X.X.X.X (i.e. 192.168.0.0 netmask 255.255.255.0)
      - A.B.C.D - E.F.G.D (i.e. 192-168.0.0-192.168.0.255)
      - A.B.C.D
    returns a named tuple with networks start and network end
    '''

    inputString = strNets
    logger.debug('Getting network from %s', strNets)

    def check(*args) -> None:
        for n in args:
            if int(n) < 0 or int(n) > 255:
                raise Exception()

    def toNum(*args) -> int:
        start = 256 * 256 * 256
        val = 0
        for n in args:
            val += start * int(n)
            start >>= 8
        return val

    def maskFromBits(nBits: int) -> int:
        v = 0
        for n in range(nBits):
            v |= 1 << (31 - n)
        return v

    strNets = strNets.replace(' ', '')

    if strNets == '*':
        return NetworkType(0, 2**32 - 1, 4)

    try:
        # Test patterns
        m = reCIDRIPv4.match(strNets)
        if m is not None:
            logger.debug('Format is CIDR')
            check(*m.groups())
            bits = int(m.group(5))
            if bits < 0 | bits > 32:
                raise Exception()
            val = toNum(*m.groups())
            bits = maskFromBits(bits)
            noBits = ~bits & 0xFFFFFFFF
            return NetworkType(val & bits, val | noBits, 4)

        m = reMaskIPv4.match(strNets)
        if m is not None:
            logger.debug('Format is network mask')
            check(*m.groups())
            val = toNum(*(m.groups()[0:4]))
            bits = toNum(*(m.groups()[4:8]))
            noBits = ~bits & 0xFFFFFFFF
            return NetworkType(val & bits, val | noBits, 4)

        m = reRangeIPv4.match(strNets)
        if m is not None:
            logger.debug('Format is network range')
            check(*m.groups())
            val = toNum(*(m.groups()[0:4]))
            val2 = toNum(*(m.groups()[4:8]))
            if val2 < val:
                raise Exception()
            return NetworkType(val, val2, 4)

        m = reSingleIPv4.match(strNets)
        if m is not None:
            logger.debug('Format is a single host')
            check(*m.groups())
            val = toNum(*m.groups())
            return NetworkType(val, val, 4)

        for v in ((re1AsteriskIPv4, 3), (re2AsteriskIPv4, 2), (re3AsteriskIPv4, 1)):
            m = v[0].match(strNets)
            if m is not None:
                check(*m.groups())
                val = toNum(*(m.groups()[0 : v[1] + 1]))
                bits = maskFromBits(v[1] * 8)
                noBits = ~bits & 0xFFFFFFFF
                return NetworkType(val & bits, val | noBits, 4)

        # No pattern recognized, invalid network
        raise Exception()
    except Exception as e:
        logger.error('Invalid network found: %s %s', strNets, e)
        raise ValueError(inputString) from e


def networkFromStringIPv6(strNets: str) -> NetworkType:
    '''
    returns a named tuple with networks start and network end
    '''
    logger.debug('Getting network from %s', strNets)

    # if '*' or '::*', return the whole IPv6 range
    if strNets in ('*', '::*'):
        return NetworkType(0, 2**128 - 1, 6)

    try:
        # using ipaddress module
        net = ipaddress.ip_network(strNets, strict=False)
        return NetworkType(int(net.network_address), int(net.broadcast_address), 6)
    except Exception as e:
        logger.error('Invalid network found: %s %s', strNets, e)
        raise ValueError(strNets) from e


def networkFromString(
    strNets: str,
    version: typing.Literal[0, 4, 6] = 0,
) -> NetworkType:
    if not ':' in strNets and version != 6:
        return networkFromStringIPv4(strNets)
    # ':' in strNets or version == 6:
    # If is in fact an IPv4 address, return None network, this will not be used
    if '.' in strNets:
        return NetworkType(0, 0, 0)
    return networkFromStringIPv6(strNets)


def networksFromString(
    nets: str,
    version: typing.Literal[0, 4, 6] = 0,
) -> typing.List[NetworkType]:
    """
    If allowMultipleNetworks is True, it allows ',' and ';' separators (and, ofc, more than 1 network)
    Returns a list of networks tuples in the form [(start1, end1), (start2, end2) ...]
    """
    res = []
    for strNet in re.split('[;,]', nets):
        if strNet:
            res.append(networkFromString(strNet, version))
    return res


def contains(
    networks: typing.Union[str, NetworkType, typing.List[NetworkType]],
    ip: typing.Union[str, int],
    version: typing.Literal[0, 4, 6] = 0,
) -> bool:
    if isinstance(ip, str):
        ip, version = ipToLong(ip)  # Ip overrides protocol version
    if isinstance(networks, str):
        if networks == '*':
            return True  # All IPs are in the * network
        networks = networksFromString(networks, version)
    elif isinstance(networks, NetworkType):
        networks = [networks]

    # Ensure that the IP is in the same family as the network on checks
    for net in networks:
        if net.start <= ip <= net.end:
            return True
    return False


def isValidIp(value: str, version: typing.Literal[0, 4, 6] = 0) -> bool:
    # Using ipaddress module
    try:
        addr = ipaddress.ip_address(value)
        return version in (0, addr.version)  # Must be the same version or 0
    except ValueError:
        return False


def isValidFQDN(value: str) -> bool:
    return (
        re.match(
            r'^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$',
            value,
        )
        is not None
    )


def isValidHost(value: str):
    return isValidIp(value) or isValidFQDN(value)


def testConnection(host: str, port: typing.Union[int, str], timeOut: float = 4) -> bool:
    try:
        logger.debug(
            'Checking connection to %s:%s with %s seconds timeout', host, port, timeOut
        )
        sock = socket.create_connection((host, int(port)), timeOut)
        sock.close()
    except Exception as e:
        logger.debug(
            'Exception checking %s:%s with %s timeout: %s', host, port, timeOut, e
        )
        return False
    return True
