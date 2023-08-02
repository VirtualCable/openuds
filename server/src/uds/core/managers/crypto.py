# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import hashlib
import array
import uuid
import codecs
import datetime
import struct
import re
import string
import logging
import typing
import secrets

# For password secrets
from argon2 import PasswordHasher

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from django.conf import settings

from uds.core.util import singleton

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.asymmetric.dsa import DSAPrivateKey
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
    from cryptography.hazmat.primitives.asymmetric.dh import DHPrivateKey


UDSK: typing.Final[bytes] = settings.SECRET_KEY[8:24].encode()  # UDS key, new


class CryptoManager(metaclass=singleton.Singleton):
    _rsa: 'RSAPrivateKey'
    _namespace: uuid.UUID

    def __init__(self) -> None:
        self._rsa = serialization.load_pem_private_key(
            settings.RSA_KEY.encode(), password=None, backend=default_backend()
        )
        self._namespace = uuid.UUID('627a37a5-e8db-431a-b783-73f7d20b4934')

    @staticmethod
    def AESKey(key: typing.Union[str, bytes], length: int) -> bytes:
        if isinstance(key, str):
            key = key.encode('utf8')

        while len(key) < length:
            key += key  # Dup key

        kl: typing.List[int] = list(key)
        pos = 0
        while len(kl) > length:
            kl[pos] ^= kl[length]
            pos = (pos + 1) % length
            del kl[length]

        return bytes(kl)

    @staticmethod
    def manager() -> 'CryptoManager':
        return CryptoManager()  # Singleton pattern will return always the same instance

    def encrypt(self, value: str) -> str:
        return codecs.encode(
            self._rsa.public_key().encrypt(
                value.encode(),
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            ),
            'base64',
        ).decode()

    def decrypt(self, value: str) -> str:
        data: bytes = codecs.decode(value.encode(), 'base64')

        try:
            # First, try new "cryptografy" decrpypting
            decrypted: bytes = self._rsa.decrypt(
                data,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
        except Exception:  # Old method is not supported
            logger.exception('Decripting: %s', value)
            return 'decript error'
        # logger.debug('Decripted: %s %s', data, decrypted)
        return decrypted.decode()

    def AESCrypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        # First, match key to 16 bytes. If key is over 16, create a new one based on key of 16 bytes length
        cipher = Cipher(
            algorithms.AES(CryptoManager.AESKey(key, 16)),
            modes.CBC(b'udsinitvectoruds'),
            backend=default_backend(),
        )
        rndStr = secrets.token_bytes(16)  # Same as block size of CBC (that is 16 here)
        paddedLength = ((len(text) + 4 + 15) // 16) * 16
        toEncode = (
            struct.pack('>i', len(text)) + text + rndStr[: paddedLength - len(text) - 4]
        )
        encryptor = cipher.encryptor()
        encoded = encryptor.update(toEncode) + encryptor.finalize()

        if base64:
            encoded = codecs.encode(encoded, 'base64').strip()  # Return as bytes

        return encoded

    def AESDecrypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        if base64:
            text = codecs.decode(text, 'base64')

        cipher = Cipher(
            algorithms.AES(CryptoManager.AESKey(key, 16)),
            modes.CBC(b'udsinitvectoruds'),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        toDecode = decryptor.update(text) + decryptor.finalize()
        return toDecode[4 : 4 + struct.unpack('>i', toDecode[:4])[0]]

    # Fast encription using django SECRET_KEY as key
    def fastCrypt(self, data: bytes) -> bytes:
        return self.AESCrypt(data, UDSK)

    # Fast decryption using django SECRET_KEY as key
    def fastDecrypt(self, data: bytes) -> bytes:
        return self.AESDecrypt(data, UDSK)

    def xor(
        self, value: typing.Union[str, bytes], key: typing.Union[str, bytes]
    ) -> bytes:
        if not key:
            return b''  # Protect against division by cero

        if isinstance(value, str):
            value = value.encode('utf-8')
        if isinstance(key, str):
            key = key.encode('utf-8')
        mult = len(value) // len(key) + 1
        value_array = array.array('B', value)
        key_array = array.array(
            'B', key * mult
        )  # Ensure key array is at least as long as value_array
        # We must return binary in xor, because result is in fact binary
        return array.array(
            'B', (value_array[i] ^ key_array[i] for i in range(len(value_array)))
        ).tobytes()

    def symCrypt(
        self, text: typing.Union[str, bytes], key: typing.Union[str, bytes]
    ) -> bytes:
        if isinstance(text, str):
            text = text.encode()
        if isinstance(key, str):
            key = key.encode()

        return self.AESCrypt(text, key)

    def symDecrpyt(
        self, cryptText: typing.Union[str, bytes], key: typing.Union[str, bytes]
    ) -> str:
        if isinstance(cryptText, str):
            cryptText = cryptText.encode()

        if isinstance(key, str):
            key = key.encode()

        if not cryptText or not key:
            return ''

        try:
            return self.AESDecrypt(cryptText, key).decode('utf-8')
        except Exception:  # Error decoding crypted element, return empty one
            return ''

    def loadPrivateKey(
        self, rsaKey: str
    ) -> typing.Union[
        'RSAPrivateKey', 'DSAPrivateKey', 'DHPrivateKey', 'EllipticCurvePrivateKey'
    ]:
        try:
            return serialization.load_pem_private_key(
                rsaKey.encode(), password=None, backend=default_backend()
            )
        except Exception as e:
            raise e

    def loadCertificate(
        self, certificate: typing.Union[str, bytes]
    ) -> x509.Certificate:
        if isinstance(certificate, str):
            certificate = certificate.encode()

        # If invalid certificate, will raise an exception
        try:
            return x509.load_pem_x509_certificate(certificate, default_backend())
        except Exception as e:
            raise Exception('Invalid certificate') from e

    def certificateString(self, certificate: str) -> str:
        # Remove -----.*-----\n strings using regex
        return re.sub(r'(-----.*-----\n)', '', certificate)

    def secret(self, length: int = 16) -> str:
        """
        Get a random secret string from config.SECRET_KEY
        """
        return settings.SECRET_KEY[:length]

    def salt(self, length: int = 16) -> str:
        """
        Get a random salt random string
        """
        return secrets.token_hex(length)

    def hash(self, value: typing.Union[str, bytes]) -> str:
        if isinstance(value, str):
            value = value.encode()

        # Argon2
        return '{ARGON2}' + PasswordHasher().hash(value.decode())

    def checkHash(self, value: typing.Union[str, bytes], hashValue: str) -> bool:
        if isinstance(value, str):
            value = value.encode()

        if not value:
            return not hashValue

        if hashValue[:8] == '{SHA256}':
            return secrets.compare_digest(
                hashlib.sha3_256(value).hexdigest(), hashValue[8:]
            )
        if hashValue[:12] == '{SHA256SALT}':
            # Extract 16 chars salt and hash
            salt = hashValue[12:28].encode()
            value = salt + value
            return secrets.compare_digest(
                hashlib.sha3_256(value).hexdigest(), hashValue[28:]
            )
        # Argon2
        if hashValue[:8] == '{ARGON2}':
            ph = PasswordHasher()
            try:
                ph.verify(hashValue[8:], value.decode())
                return True
            except Exception:
                return False  # Verify will raise an exception if not valid

        # Old sha1
        return secrets.compare_digest(
            hashValue, str(hashlib.sha1(value).hexdigest())  # nosec: Old compatibility SHA1, not used anymore but need to be supported
        )  # nosec: Old compatibility SHA1, not used anymore but need to be supported

    def uuid(self, obj: typing.Any = None) -> str:
        """ Generates an uuid from obj. (lower case)
        If obj is None, returns an uuid based on a random string
        """
        if obj is None:
            obj = self.randomString()
        elif isinstance(obj, bytes):
            obj = obj.decode('utf8')  # To string
        else:
            obj = str(obj)

        return str(
            uuid.uuid5(self._namespace, obj)
        ).lower()  # I believe uuid returns a lowercase uuid always, but in case... :)

    def randomString(self, length: int = 40, digits: bool = True) -> str:
        base = string.ascii_letters + (string.digits if digits else '')
        return ''.join(secrets.choice(base) for _ in range(length))

    def unique(self) -> str:
        return hashlib.sha3_256(
            (
                self.randomString(24, True)
                + datetime.datetime.now().strftime('%H%M%S%f')
            ).encode()
        ).hexdigest()
