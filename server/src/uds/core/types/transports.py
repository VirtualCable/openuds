# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.U.
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
import codecs
import collections.abc
import dataclasses
import enum
import json
import typing


class Protocol(enum.StrEnum):
    NONE = ''
    RDP = 'rdp'
    RDS = 'rds'  # In fact, RDS (Remote Desktop Services) is RDP, but have "more info" for connection that RDP
    SPICE = 'spice'
    VNC = 'vnc'
    PCOIP = 'pcoip'
    REMOTEFX = 'remotefx'  # This in fact is RDP als
    HDX = 'hdx'
    ICA = 'ica'
    NX = 'nx'
    X11 = 'x11'
    X2GO = 'x2go'  # Based on NX
    NICEDCV = 'nicedcv'
    SSH = 'ssh'
    OTHER = 'other'

    @staticmethod
    def generic_vdi(*extra: 'Protocol') -> typing.Tuple['Protocol', ...]:
        return (
            Protocol.RDP,
            Protocol.VNC,
            Protocol.NX,
            Protocol.X11,
            Protocol.X2GO,
            Protocol.PCOIP,
            Protocol.NICEDCV,
            Protocol.SSH,
            Protocol.OTHER,
        ) + extra


@dataclasses.dataclass
class TransportScript:
    script: str = ''
    # currently only python is supported
    script_type: typing.Literal['python'] = 'python'
    signature_b64: str = ''  # Signature of the script in base64
    parameters: collections.abc.Mapping[str, typing.Any] = dataclasses.field(default_factory=dict)

    @property
    def encoded_parameters(self) -> str:
        """
        Returns encoded parameters for transport script
        """
        return codecs.encode(codecs.encode(json.dumps(self.parameters).encode(), 'bz2'), 'base64').decode()
