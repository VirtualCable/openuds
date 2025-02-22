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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import functools
import ipaddress
import logging
import re
import socket
import typing


class IpType(typing.NamedTuple):
    ip: int
    version: typing.Literal[4, 6, 0]  # 0 is only used for invalid detected ip


class NetworkType(typing.NamedTuple):
    start: int
    end: int
    version: typing.Literal[0, 4, 6]  # 4 or 6


logger = logging.getLogger(__name__)

# Test patters for networks IPv4
RECIDRIPV4: typing.Final[re.Pattern[str]] = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})/([0-9]{1,2})$'
)
REMASKIPV4: typing.Final[re.Pattern[str]] = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})netmask([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
)
RE1ASTERISKIPV4: typing.Final[re.Pattern[str]] = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.\*$')
RE2ASTERISKIPV4: typing.Final[re.Pattern[str]] = re.compile(r'^([0-9]{1,3})\.([0-9]{1,3})\.\*\.?\*?$')
RE3ASTERISKIPV4: typing.Final[re.Pattern[str]] = re.compile(r'^([0-9]{1,3})\.\*\.?\*?\.?\*?$')
RERANGEIPV4: typing.Final[re.Pattern[str]] = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})-([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
)
RESINGLEIPV4: typing.Final[re.Pattern[str]] = re.compile(
    r'^([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,3})$'
)


def ip_to_long(ip: str) -> IpType:
    """
    Convert an ipv4 or ipv6 address to its long representation
    """
    # First, check if it's an ipv6 address
    try:
        if ':' in ip:
            if '.' in ip:  # Is , for example, '::ffff:172.27.0.1'
                ip = ip.split(':')[-1]
            else:
                return IpType(int(ipaddress.IPv6Address(ip)), 6)
        return IpType(int(ipaddress.IPv4Address(ip)), 4)
    except Exception as e:
        logger.error('Ivalid value: %s (%s)', ip, e)
        return IpType(0, 0)  # Invalid values will map to "0.0.0.0" --> 0


def long_to_ip(n: int, version: typing.Literal[0, 4, 6] = 0) -> str:
    """
    convert long int to ipv4 or ipv6 address, depending on size
    """
    if n > 2**32 or version == 6:
        return str(ipaddress.IPv6Address(n).compressed)
    return str(ipaddress.IPv4Address(n))


def network_from_str_ipv4(nets_string: str) -> NetworkType:
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

    input_string = nets_string
    logger.debug('Getting network from %s', nets_string)

    def check(*args: str) -> None:
        for n in args:
            if int(n) < 0 or int(n) > 255:
                raise Exception()

    def to_num(*args: str) -> int:
        start = 256 * 256 * 256
        val = 0
        for n in args:
            val += start * int(n)
            start >>= 8
        return val

    def mask_from_bits(nBits: int) -> int:
        v = 0
        for n in range(nBits):
            v |= 1 << (31 - n)
        return v

    nets_string = nets_string.replace(' ', '')

    if nets_string == '*':
        return NetworkType(0, 2**32 - 1, 4)

    try:
        # Test patterns
        m = RECIDRIPV4.match(nets_string)
        if m is not None:
            logger.debug('Format is CIDR')
            check(*m.groups())
            bits = int(m.group(5))
            if bits < 0 | bits > 32:
                raise Exception()
            val = to_num(*m.groups())
            bits = mask_from_bits(bits)
            negated_bits = ~bits & 0xFFFFFFFF
            return NetworkType(val & bits, val | negated_bits, 4)

        m = REMASKIPV4.match(nets_string)
        if m is not None:
            logger.debug('Format is network mask')
            check(*m.groups())
            val = to_num(*(m.groups()[0:4]))
            bits = to_num(*(m.groups()[4:8]))
            negated_bits = ~bits & 0xFFFFFFFF
            return NetworkType(val & bits, val | negated_bits, 4)

        m = RERANGEIPV4.match(nets_string)
        if m is not None:
            logger.debug('Format is network range')
            check(*m.groups())
            val = to_num(*(m.groups()[0:4]))
            val2 = to_num(*(m.groups()[4:8]))
            if val2 < val:
                raise Exception()
            return NetworkType(val, val2, 4)

        m = RESINGLEIPV4.match(nets_string)
        if m is not None:
            logger.debug('Format is a single host')
            check(*m.groups())
            val = to_num(*m.groups())
            return NetworkType(val, val, 4)

        for v in ((RE1ASTERISKIPV4, 3), (RE2ASTERISKIPV4, 2), (RE3ASTERISKIPV4, 1)):
            m = v[0].match(nets_string)
            if m is not None:
                check(*m.groups())
                val = to_num(*(m.groups()[0 : v[1] + 1]))
                bits = mask_from_bits(v[1] * 8)
                negated_bits = ~bits & 0xFFFFFFFF
                return NetworkType(val & bits, val | negated_bits, 4)

        # No pattern recognized, invalid network
        raise Exception()
    except Exception as e:
        logger.error('Invalid network found: %s %s', nets_string, e)
        raise ValueError(input_string) from e


def network_from_str_ipv6(networks: str) -> NetworkType:
    '''
    returns a named tuple with networks start and network end
    '''
    logger.debug('Getting network from %s', networks)

    # if '*' or '::*', return the whole IPv6 range
    if networks in ('*', '::*'):
        return NetworkType(0, 2**128 - 1, 6)

    try:
        # using ipaddress module
        net = ipaddress.ip_network(networks, strict=False)
        return NetworkType(int(net.network_address), int(net.broadcast_address), 6)
    except Exception as e:
        logger.error('Invalid network found: %s %s', networks, e)
        raise ValueError(networks) from e


def network_from_str(
    network_str: str,
    version: typing.Literal[0, 4, 6] = 0,
    *,
    check_mode: bool = False,
) -> NetworkType:
    try:
        if not ':' in network_str and version != 6:
            return network_from_str_ipv4(network_str)
        # ':' in strNets or version == 6:
        # If is in fact an IPv4 address, return None network, this will not be used
        if '.' in network_str:
            return NetworkType(0, 0, 0)
        return network_from_str_ipv6(network_str)
    except ValueError:
        if check_mode:
            raise
        return NetworkType(0, 0, 0)


@functools.lru_cache(maxsize=32)
def networks_from_str(
    networks_str: str,
    version: typing.Literal[0, 4, 6] = 0,
    *,
    check_mode: bool = False,
) -> list[NetworkType]:
    """
    Converts a string with networks to a list of NetworkType

    Args:
        networks_str: A string with networks separated by ',' or ';'
        version: The version of the networks to convert. If 0, it will try to detect the version
        check_mode: If True, it will raise an exception if a network is invalid (default is False).

    Returns:
        a list of NetworkType containing the networks (only valid networks are returned)

    Raises:
        ValueError: If a network is invalid and check_mode is True

    Returns a list of networks tuples in the form [(start1, end1), (start2, end2) ...]
    """
    return [
        network_from_str(str_net, version, check_mode=check_mode)
        for str_net in re.split('[;,]', networks_str)
        if str_net
    ]


def contains(
    networks: typing.Union[str, NetworkType, list[NetworkType]],
    ip: typing.Union[str, int],
    version: typing.Literal[0, 4, 6] = 0,
) -> bool:
    """
    Checks if an IP is contained in a network or list of networks.
    In case of string, the networks are separated by ',' or ';' and if any network is invalid,
    will simply be ignored.

    Args:
        networks: A string with networks separated by ',' or ';' or a list of NetworkType
        ip: The IP to check. if it's an string, the version will be detected.
        version: The version of the IP to check. If 0, it will try to detect the version

    Returns:
        True if the IP is contained in any of the networks, False otherwise

    """
    if isinstance(ip, str):
        ip, version = ip_to_long(ip)  # Ip overrides protocol version
    if isinstance(networks, str):
        if networks == '*':
            return True  # All IPs are in the * network
        networks = networks_from_str(networks, version)
    elif isinstance(networks, NetworkType):
        networks = [networks]

    # Ensure that the IP is in the same family as the network on checks
    for net in networks:
        if net.start <= ip <= net.end:
            return True
    return False


def is_valid_ip(value: str, version: typing.Literal[0, 4, 6] = 0) -> bool:
    """
    Checks if a value is a valid IP address of the specified version

    Args:
        value: The value to check
        version: The version of the IP to check. If 0, it will try to detect the version

    Returns:
        True if the value is a valid IP address, False otherwise
    """
    try:
        addr = ipaddress.ip_address(value)
        return version in (0, addr.version)  # Must be the same version or 0
    except ValueError:
        return False


def is_valid_fqdn(fqdn: str) -> bool:
    """
    Checks if a value is a valid Fully Qualified Domain Name (FQDN)

    Args:
        value: The value to check

    Returns:
        True if the value is a valid FQDN, False otherwise
    """
    return (
        re.match(r'^(?!:\/\/)(?=.{1,255}$)((.{1,63}\.){1,127}(?![0-9]*$)[a-z0-9-]+\.?)$', fqdn, re.IGNORECASE)
        is not None  # Allow for non qualified domain names (such as localhost, host1, etc)
        or re.match(r'^[a-z0-9-]+$', fqdn, re.IGNORECASE) is not None
    )


def is_valid_host(host: str) -> bool:
    """
    Checks if a value is a valid IP address or FQDN

    Args:
        host: The value to check (IP address or FQDN)

    Returns:
        True if the value is a valid IP address or FQDN, False otherwise
    """
    return is_valid_ip(host) or is_valid_fqdn(host)


def is_valid_mac(value: str) -> bool:
    """
    Checks if a value is a valid MAC address

    Args:
        value: The value to check

    Returns:
        True if the value is a valid MAC address, False otherwise
    """
    return re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', value) is not None


def test_connectivity(host: str, port: int, timeout: float = 4) -> bool:
    """
    Checks the connectivity to a host and port
    
    Args:
        host: The host to check
        port: The port to check
        timeout: The timeout in seconds for the connection (default is 4 seconds)
        
    Returns:
        True if the connection is successful, False otherwise
    """
    try:
        logger.debug('Checking connection to %s:%s with %s seconds timeout', host, port, timeout)
        sock = socket.create_connection((host, port), timeout)
        sock.close()
    except Exception as e:
        logger.debug('Exception checking %s:%s with %s timeout: %s', host, port, timeout, e)
        return False
    return True
