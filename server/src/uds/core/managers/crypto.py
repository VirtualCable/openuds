# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import hashlib
import array
import uuid
import struct
import random
import string
import logging
import typing

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# Deprecating these. On future versions will only use
# cryptography libraries. Keep here for backwards compat with
# 1.x 2.x encriptions methods
from Crypto.PublicKey import RSA
from Crypto.Random import atfork # type: ignore

from django.conf import settings

from uds.core.util import encoders

logger = logging.getLogger(__name__)

class CryptoManager:
    instance = None

    def __init__(self):
        self._rsa = serialization.load_pem_private_key(settings.RSA_KEY.encode(), password=None, backend=default_backend())
        self._oldRsa = RSA.importKey(settings.RSA_KEY)
        self._namespace = uuid.UUID('627a37a5-e8db-431a-b783-73f7d20b4934')
        self._counter = 0

    @staticmethod
    def AESKey(key: typing.Union[str, bytes], length: int) -> bytes:
        if isinstance(key, str):
            key = key.encode('utf8')

        while len(key) < length:
            key += key  # Dup key

        kl: typing.List[int] = [v for v in key]
        pos = 0
        while len(kl) > length:
            kl[pos] ^= kl[length]
            pos = (pos + 1) % length
            del kl[length]

        return bytes(kl)

    @staticmethod
    def manager() -> 'CryptoManager':
        if CryptoManager.instance is None:
            CryptoManager.instance = CryptoManager()
        return CryptoManager.instance

    def encrypt(self, value: typing.Union[str, bytes]) -> str:
        if isinstance(value, str):
            value = value.encode('utf-8')

        return encoders.encodeAsStr(
            self._rsa.public_key().encrypt(
                value,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            ),
            'base64'
        )

        # atfork()
        # return typing.cast(str, encoders.encode((self._rsa.encrypt(value, b'')[0]), 'base64', asText=True))


    def decrypt(self, value: typing.Union[str, bytes]) -> str:
        if isinstance(value, str):
            value = value.encode('utf-8')

        data: bytes = typing.cast(bytes, encoders.decode(value, 'base64'))
        decrypted: bytes

        try:
            # First, try new "cryptografy" decrpypting
            decrypted = self._rsa.decrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
        except Exception:  # If fails, try old method
            try:
                atfork()
                decrypted = self._oldRsa.decrypt(encoders.decode(value, 'base64'))
            except Exception:
                logger.exception('Decripting: %s', value)
                # logger.error(inspect.stack())
                return 'decript error'
        # logger.debug('Decripted: %s %s', data, decrypted)
        return decrypted.decode()

    def AESCrypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        # First, match key to 16 bytes. If key is over 16, create a new one based on key of 16 bytes length
        cipher = Cipher(algorithms.AES(CryptoManager.AESKey(key, 16)), modes.CBC(b'udsinitvectoruds'), backend=default_backend())
        rndStr = self.randomString(16).encode()  # Same as block size of CBC (that is 16 here)
        paddedLength = ((len(text) + 4 + 15) // 16) * 16
        toEncode = struct.pack('>i', len(text)) + text + rndStr[:paddedLength - len(text) - 4]
        encryptor = cipher.encryptor()
        encoded = encryptor.update(toEncode) + encryptor.finalize()
        
        if base64:
            return typing.cast(bytes, encoders.encode(encoded, 'base64'))  # Return as binary

        return encoded

    def AESDecrypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        if base64:
            text = typing.cast(bytes, encoders.decode(text, 'base64'))

        cipher = Cipher(algorithms.AES(CryptoManager.AESKey(key, 16)), modes.CBC(b'udsinitvectoruds'), backend=default_backend())
        decryptor = cipher.decryptor()

        toDecode = decryptor.update(text) + decryptor.finalize()
        return toDecode[4:4 + struct.unpack('>i', toDecode[:4])[0]]

    def xor(self, s1: typing.Union[str, bytes], s2: typing.Union[str, bytes]) -> bytes:
        if isinstance(s1, str):
            s1 = s1.encode('utf-8')
        if isinstance(s2, str):
            s2 = s2.encode('utf-8')
        mult = len(s1) // len(s2) + 1
        s1a = array.array('B', s1)
        s2a = array.array('B', s2 * mult)
        # We must return bynary in xor, because result is in fact binary
        return array.array('B', (s1a[i] ^ s2a[i] for i in range(len(s1a)))).tobytes()

    def symCrypt(self, text: typing.Union[str, bytes], key: typing.Union[str, bytes]) -> bytes:
        return self.xor(text, key)

    def symDecrpyt(self, cryptText: typing.Union[str, bytes], key: typing.Union[str, bytes]) -> str:
        return self.xor(cryptText, key).decode('utf-8')

    def loadPrivateKey(self, rsaKey: str):
        try:
            pk = RSA.importKey(rsaKey)
        except Exception as e:
            raise e
        return pk

    def loadCertificate(self, certificate: typing.Union[str, bytes]):
        if isinstance(certificate, str):
            certificate = certificate.encode()

        # If invalid certificate, will raise an exception
        try:
            return x509.load_pem_x509_certificate(certificate, default_backend())
        except Exception:
            raise Exception('Invalid certificate')

    def certificateString(self, certificate: str) -> str:
        return certificate.replace('-----BEGIN CERTIFICATE-----', '').replace('-----END CERTIFICATE-----', '').replace('\n', '')

    def hash(self, value: typing.Union[str, bytes]) -> str:
        if isinstance(value, str):
            value = value.encode('utf-8')

        if not value:
            return ''

        return str(hashlib.sha1(value).hexdigest())

    def uuid(self, obj: typing.Any = None) -> str:
        """
        Generates an uuid from obj. (lower case)
        If obj is None, returns an uuid based on current datetime + counter
        """
        if obj is None:
            obj = self.randomString()
            self._counter += 1
        elif isinstance(obj, bytes):
            obj = obj.decode('utf8')  # To binary
        else:
            obj = '{}'.format(obj)

        return str(uuid.uuid5(self._namespace, obj)).lower()  # I believe uuid returns a lowercase uuid always, but in case... :)

    def randomString(self, length: int = 40) -> str:
        return ''.join(random.SystemRandom().choices(string.ascii_lowercase + string.digits, k=length))
