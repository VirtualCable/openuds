# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.
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
'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import platform
import socket
import fcntl
import struct
import array
import typing

from uds.core import consts, types


def list_ifaces() -> typing.Iterator[types.net.Iface]:
    def _get_iface_mac_addr(ifname: str) -> typing.Optional[str]:
        '''
        Returns the mac address of an interface
        Mac is returned as unicode utf-8 encoded
        '''
        ifnameBytes = ifname.encode('utf-8')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            info = bytearray(fcntl.ioctl(s.fileno(), 0x8927, struct.pack(str('256s'), ifnameBytes[:15])))
            return str(''.join(['%02x:' % char for char in info[18:24]])[:-1]).upper()
        except Exception:
            return None

    def _get_iface_ip_addr(ifname: str) -> typing.Optional[str]:
        '''
        Returns the ip address of an interface
        Ip is returned as unicode utf-8 encoded
        '''
        ifnameBytes = ifname.encode('utf-8')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return str(
                socket.inet_ntoa(
                    fcntl.ioctl(
                        s.fileno(),
                        0x8915,  # SIOCGIFADDR
                        struct.pack(str('256s'), ifnameBytes[:15]),
                    )[20:24]
                )
            )
        except Exception:
            return None

    def _list_ifaces() -> list[str]:
        '''
        Returns a list of interfaces names coded in utf-8
        '''
        max_possible = 128  # arbitrary. raise if needed.
        space = max_possible * 16
        if platform.architecture()[0] == '32bit':
            offset, length = 32, 32
        elif platform.architecture()[0] == '64bit':
            offset, length = 16, 40
        else:
            raise OSError('Unknown arquitecture {0}'.format(platform.architecture()[0]))

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        names = array.array(str('B'), b'\0' * space)
        outbytes = struct.unpack(
            'iL',
            fcntl.ioctl(
                s.fileno(),
                0x8912,  # SIOCGIFCONF
                struct.pack('iL', space, names.buffer_info()[0]),
            ),
        )[0]
        namestr = names.tobytes()
        # return namestr, outbytes
        return [namestr[i : i + offset].split(b'\0', 1)[0].decode('utf-8') for i in range(0, outbytes, length)]

    for ifname in _list_ifaces():
        ip, mac = _get_iface_ip_addr(ifname), _get_iface_mac_addr(ifname)
        if (
            mac != consts.NULL_MAC and mac and ip and ip.startswith('169.254') is False
        ):  # Skips local interfaces & interfaces with no dhcp IPs
            yield types.net.Iface(name=ifname, mac=mac, ip=ip)

def get_first_iface() -> typing.Optional[types.net.Iface]:
    """
    Returns the first interface found, or None if no interface is found.
    """
    try:
        return next(list_ifaces())
    except StopIteration:
        return None