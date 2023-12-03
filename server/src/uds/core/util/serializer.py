# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import typing
import collections.abc
import pickle  # nosec:  Used with care :)
import lzma

from uds.core.managers.crypto import CryptoManager

CURRENT_SERIALIZER_VERSION = b'v1'
DESERIALIZERS: typing.Final[collections.abc.Mapping[bytes, collections.abc.Callable[[bytes], bytes]]] = {
    b'v1': CryptoManager().fastDecrypt,
}


def serialize(obj: typing.Any) -> bytes:
    """
    Serializes an object to a json string
    """
    # generate pickle dump and encrypt it to keep it safe
    # Compress data using lzma first

    data = CryptoManager().fastCrypt(
        lzma.compress(pickle.dumps(obj))
    )  # With latest available protocol
    return CURRENT_SERIALIZER_VERSION + data


def deserialize(data: typing.Optional[bytes]) -> typing.Any:
    """
    Deserializes an object from a json string
    """
    if not data:
        return None

    if data[0:2] in DESERIALIZERS:
        return pickle.loads(
            lzma.decompress(DESERIALIZERS[data[0:2]](data[2:]))
        )  # nosec:  Secured by encryption
    # Old version, try to unpickle it
    try:
        return pickle.loads(data)  # nosec:  Backward compatibility
    except Exception:
        return None
