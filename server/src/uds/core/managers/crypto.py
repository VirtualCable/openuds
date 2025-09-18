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
Author: Adolfo Gómez, dkmaster at dkmon dot com
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
import base64


uuid7: None|typing.Callable[[], 'uuid.UUID']
try:
    from edwh_uuid7 import uuid7  # type: ignore
except ImportError:
    uuid7 = None  # type: ignore

# For password secrets
from argon2 import PasswordHasher, Type as ArgonType

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes, aead


from django.conf import settings

from uds.core.util import singleton

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
    from cryptography.hazmat.primitives.asymmetric.dsa import DSAPrivateKey
    from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
    from cryptography.hazmat.primitives.asymmetric.dh import DHPrivateKey

# Note the REAL BIG importance of the SECRET_KEY. if lost, all encripted stored data (almost all fields) will be lost...
UDSK: typing.Final[bytes] = settings.SECRET_KEY[
    8:24
].encode()  # UDS key, new, for AES256, so it's 16 bytes length


class CryptoManager(metaclass=singleton.Singleton):
    _rsa: 'RSAPrivateKey'
    _namespace: uuid.UUID

    def __init__(self) -> None:
        self._rsa = typing.cast(
            'RSAPrivateKey',
            serialization.load_pem_private_key(
                settings.RSA_KEY.encode(), password=None, backend=default_backend()
            ),
        )
        self._namespace = uuid.UUID('627a37a5-e8db-431a-b783-73f7d20b4934')

    @staticmethod
    def manager() -> 'CryptoManager':
        return CryptoManager()  # Singleton pattern will return always the same instance

    @staticmethod
    def aes_key(key: typing.Union[str, bytes], length: int) -> bytes:
        """
        Generate an AES key of the specified length using the provided key.

        This method is used to generate an AES key of the specified length using the provided key.

        Args:
            key (Union[str, bytes]): The key used to generate the AES key. It can be either a string or bytes.
            length (int): The desired length of the AES key.

        Returns:
            bytes: The generated AES key.

        Raises:
            ValueError: If the length is not a positive integer.

        """
        bkey: bytes = key.encode() if isinstance(key, str) else key
        while len(bkey) < length:
            bkey += bkey

        kl: list[int] = list(bkey)
        pos = 0
        while len(kl) > length:
            kl[pos] ^= kl[length]
            pos = (pos + 1) % length
            del kl[length]

        return bytes(kl)

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

    def aes_crypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        # First, match key to 16 bytes. If key is over 16, create a new one based on key of 16 bytes length
        cipher = Cipher(
            algorithms.AES(CryptoManager.aes_key(key, 16)),
            modes.CBC(b'udsinitvectoruds'),
            backend=default_backend(),
        )
        rnd_string = secrets.token_bytes(16)  # Same as block size of CBC (that is 16 here)
        padded_length = ((len(text) + 4 + 15) // 16) * 16  # calculate padding length, 4 is for length of text
        to_encode = struct.pack('>i', len(text)) + text + rnd_string[: padded_length - len(text) - 4]
        encryptor = cipher.encryptor()
        encoded = encryptor.update(to_encode) + encryptor.finalize()

        if base64:
            encoded = codecs.encode(encoded, 'base64').strip()  # Return as bytes

        return encoded

    def aes_decrypt(self, text: bytes, key: bytes, base64: bool = False) -> bytes:
        if base64:
            text = codecs.decode(text, 'base64')

        cipher = Cipher(
            algorithms.AES(CryptoManager.aes_key(key, 16)),
            modes.CBC(b'udsinitvectoruds'),
            backend=default_backend(),
        )
        decryptor = cipher.decryptor()

        to_decode = decryptor.update(text) + decryptor.finalize()
        return to_decode[4 : 4 + struct.unpack('>i', to_decode[:4])[0]]

    # Fast encription using django SECRET_KEY as key
    def fast_crypt(self, data: bytes) -> bytes:
        return self.aes_crypt(data, UDSK)

    # Fast decryption using django SECRET_KEY as key
    def fast_decrypt(self, data: bytes) -> bytes:
        return self.aes_decrypt(data, UDSK)

    def xor(self, value: typing.Union[str, bytes], key: typing.Union[str, bytes]) -> bytes:
        if not key:
            return b''  # Protect against division by cero

        if isinstance(value, str):
            value = value.encode('utf-8')
        if isinstance(key, str):
            key = key.encode('utf-8')
        mult = len(value) // len(key) + 1
        value_array = array.array('B', value)
        # Ensure key array is at least as long as value_array
        key_array = array.array('B', key * mult)
        # We must return binary in xor, because result is in fact binary
        return array.array('B', (value_array[i] ^ key_array[i] for i in range(len(value_array)))).tobytes()

    def symmetric_encrypt(self, text: typing.Union[str, bytes], key: typing.Union[str, bytes]) -> bytes:
        if isinstance(text, str):
            text = text.encode()
        if isinstance(key, str):
            key = key.encode()

        return self.aes_crypt(text, key)

    def symmetric_decrypt(self, encrypted_text: typing.Union[str, bytes], key: typing.Union[str, bytes]) -> str:
        if isinstance(encrypted_text, str):
            encrypted_text = encrypted_text.encode()

        if isinstance(key, str):
            key = key.encode()

        if not encrypted_text or not key:
            return ''

        try:
            return self.aes_decrypt(encrypted_text, key).decode('utf-8')
        except Exception:  # Error decoding crypted element, return empty one
            return ''

    def load_private_key(
        self, rsa_key: str
    ) -> typing.Union['RSAPrivateKey', 'DSAPrivateKey', 'DHPrivateKey', 'EllipticCurvePrivateKey']:
        try:
            return typing.cast(
                typing.Union['RSAPrivateKey', 'DSAPrivateKey', 'DHPrivateKey', 'EllipticCurvePrivateKey'],
                serialization.load_pem_private_key(rsa_key.encode(), password=None, backend=default_backend()),
            )
        except Exception as e:
            raise e

    def load_certificate(self, certificate: typing.Union[str, bytes]) -> x509.Certificate:
        if isinstance(certificate, str):
            certificate = certificate.encode()

        # If invalid certificate, will raise an exception
        try:
            return x509.load_pem_x509_certificate(certificate, default_backend())
        except Exception as e:
            raise Exception('Invalid certificate') from e

    def certificate_string(self, certificate: str) -> str:
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
        return '{ARGON2}' + PasswordHasher(type=ArgonType.ID).hash(value)

    def check_hash(self, value: typing.Union[str, bytes], hash_value: str) -> bool:
        if isinstance(value, str):
            value = value.encode()

        if not value:
            return not hash_value

        if hash_value[:8] == '{SHA256}':
            return secrets.compare_digest(hashlib.sha3_256(value).hexdigest(), hash_value[8:])
        if hash_value[:12] == '{SHA256SALT}':
            # Extract 16 chars salt and hash
            salt = hash_value[12:28].encode()
            value = salt + value
            return secrets.compare_digest(hashlib.sha3_256(value).hexdigest(), hash_value[28:])
        # Argon2
        if hash_value[:8] == '{ARGON2}':
            ph = PasswordHasher()  # Type is implicit in hash
            try:
                ph.verify(hash_value[8:], value)
                return True
            except Exception:
                return False  # Verify will raise an exception if not valid

        # Old sha1
        return secrets.compare_digest(
            hash_value,
            str(
                hashlib.sha1(
                    value
                ).hexdigest()  # nosec: Old SHA1 password, not used anymore but need to be supported
            ),
        )

    def uuid(self, obj: typing.Any = None) -> str:
        """Generates an uuid from obj. (lower case)
        If obj is None, returns a non-deterministic uuid (preferably uuid7 if available, else uuid4)
        """
        if obj is None:  # Non deterministic, try to use uuid7 if available
            if uuid7 is not None:
                return str(uuid7())
            return str(uuid.uuid4())
        elif isinstance(obj, bytes):
            obj = obj.decode('utf8')  # To string
        else:
            try:
                obj = str(obj)
            except Exception:
                obj = str(hash(obj))  # Get hash of object

        return str(uuid.uuid5(self._namespace, obj))  # Uuid is always lower case

    # Used to encode fields that will go inside json
    def encrypt_field_b64(self, plaintext: str, key_ascii32: str, nonce_seq: int) -> str:
        """
        Cipher a `plaintext` with AES-256-GCM using `key_ascii32` (32 bytes ASCII)
        and a nonce of 12 bytes with last one being a simple seq, starting at 1.

        Args:
            plaintext: The plaintext to encrypt.
            key_ascii32: The 32 bytes ASCII key to use for encryption.
            nonce_seq: The nonce sequence number (1, 2, 3...).

        Returns the ciphertext+tag in standard Base64.
        """
        key_bytes = key_ascii32.encode("ascii")
        if len(key_bytes) != 32:
            raise ValueError("The key must be exactly 32 bytes ASCII")

        # Nonce is 12 bytes with the last byte = nonce_seq
        nonce = bytearray(12)
        nonce[-1] = nonce_seq  # 1, 2, 3...

        # Initialize AES-GCM
        aesgcm = aead.AESGCM(key_bytes)
        return base64.b64encode(aesgcm.encrypt(bytes(nonce), plaintext.encode("utf-8"), None)).decode()

    def random_string(self, length: int = 40, digits: bool = True, punctuation: bool = False) -> str:
        base = (
            string.ascii_letters
            + (string.digits if digits else '')
            + (string.punctuation if punctuation else '')
        )
        return ''.join(secrets.choice(base) for _ in range(length))

    def unique(self) -> str:
        return hashlib.sha3_256(
            (self.random_string(24, True) + datetime.datetime.now().strftime('%H%M%S%f')).encode()
        ).hexdigest()

    def sha(self, value: typing.Union[str, bytes]) -> str:
        if isinstance(value, str):
            value = value.encode()

        return hashlib.sha3_256(value).hexdigest()
