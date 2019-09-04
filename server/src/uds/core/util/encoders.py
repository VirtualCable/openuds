# -*- coding: utf-8 -*-

#
# Copyright (c) 2017-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import codecs

def __toBinary(data: typing.Union[str, bytes]) -> bytes:
    if isinstance(data, str):
        return data.encode('utf8')
    return data


def encode(data: typing.Union[str, bytes], encoder: str, asText: bool = False) -> typing.Union[str, bytes]:
    res = codecs.encode(__toBinary(data), encoder)  # type: ignore
    if asText:
        return res.decode('utf8')
    return res


def decode(data: typing.Union[str, bytes], encoder: str, asText: bool = False) -> typing.Union[str, bytes]:
    res = codecs.decode(__toBinary(data), encoder)
    if asText:
        return res.decode('utf8')  # type: ignore
    return res


def encodeAsStr(data: typing.Union[str, bytes], encoder: str) -> str:
    return codecs.encode(__toBinary(data), encoder).decode('utf8')   # type: ignore


def decodeAsStr(data: typing.Union[str, bytes], encoder: str) -> str:
    return codecs.decode(__toBinary(data), encoder).decode('utf8')   # type: ignore
