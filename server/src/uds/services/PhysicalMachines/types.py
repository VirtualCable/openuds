# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"u
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
import dataclasses
import logging
import typing

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class HostInfo:
    host: str
    mac: str = ''
    order: str = ''

    @staticmethod
    def from_str(data: str, overrided_order: typing.Optional[str] = None) -> 'HostInfo':
        """Extracts a HostInfo from a string
        the string is "ip;mac~order" (mac and order are optional)
        """
        ip_mac, order = (data.split('~') + [''])[:2]
        ip, mac = (ip_mac.split(';') + [''])[:2]
        return HostInfo(ip, mac, overrided_order or order)

    def as_str(self) -> str:
        if self.mac:
            return f'{self.host};{self.mac}~{self.order}'
        return f'{self.host}~{self.order}'

    @staticmethod
    def from_dict(data: typing.Dict[str, typing.Any]) -> 'HostInfo':
        return HostInfo(data['ip'], data['mac'], data['order'])

    def as_dict(self) -> typing.Dict[str, typing.Any]:
        return {'ip': self.host, 'mac': self.mac, 'order': self.order}

    def pretty_print(self) -> str:
        return f'{self.host} ({self.mac})'

    def as_identifier(self) -> str:
        if self.mac:
            return f'{self.host};{self.mac}'
        return self.host

    def __hash__(self) -> int:
        return hash(self.as_identifier())  # Hash only ip and mac (if present)

    def __eq__(self, __value: object) -> bool:
        return isinstance(__value, HostInfo) and self.as_identifier() == __value.as_identifier()
    
    def __gt__(self, __value: object) -> bool:
        return isinstance(__value, HostInfo) and self.order > __value.order

    def __str__(self) -> str:
        return self.as_str()
