# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Virtual Cable S.L.
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
from re import I
import threading
import ipaddress
import typing

from udsactor.log import logger

if typing.TYPE_CHECKING:
    from udsactor.types import InterfaceInfoType


class ScriptExecutorThread(threading.Thread):
    def __init__(self, script: str) -> None:
        super(ScriptExecutorThread, self).__init__()
        self.script = script

    def run(self) -> None:
        try:
            logger.debug('Executing script: {}'.format(self.script))
            exec(self.script, globals(), None)  # pylint: disable=exec-used
        except Exception as e:
            logger.error('Error executing script: {}'.format(e))
            logger.exception()


# Convert "X.X.X.X/X" to ipaddress.IPv4Network
def strToNoIPV4Network(net: typing.Optional[str]) -> typing.Optional[ipaddress.IPv4Network]:
    if not net:  # Empty or None
        return None
    try:
        return ipaddress.IPv4Interface(net).network
    except Exception:
        return None


def validNetworkCards(
    net: typing.Optional[str], cards: typing.Iterable['InterfaceInfoType']
) -> typing.List['InterfaceInfoType']:
    try:
        subnet = strToNoIPV4Network(net)
    except Exception as e:
        logger.error('Invalid network: {}'.format(e))
        subnet = None

    if subnet is None:
        return list(cards)

    def isValid(ip: str, subnet: ipaddress.IPv4Network) -> bool:
        if not ip:
            return False
        try:
            return ipaddress.IPv4Address(ip) in subnet
        except Exception:
            return False

    return [c for c in cards if isValid(c.ip, subnet)]
