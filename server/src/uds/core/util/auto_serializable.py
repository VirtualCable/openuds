# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com

Implements de AutoSerializable class, that allows to serialize/deserialize in a simple way
This class in incompatible with UserInterface derived classes, as it metaclass is not compatible

To use it, simple place it as first parent class, and follow by the rest of the classes to inherit from

Example: 
from uds.core.util import AutoSerializable
from uds.core import services

class UserDeploymentService(AutoSerializable, services.UserDeployment):
    ...


"""

import itertools
import typing
import logging
import json
import zlib
import base64
import hashlib
import struct

# Import the cryptography library
from cryptography import fernet

from django.conf import settings


class _Unassigned:
    pass


# means field has no default value
UNASSIGNED = _Unassigned()

T = typing.TypeVar('T')
DefaultValueType = typing.Union[T, typing.Callable[[], T], _Unassigned]

logger = logging.getLogger(__name__)

# Constants

# Headers for the serialized data
HEADER_BASE: typing.Final[bytes] = b'MGB1'
HEADER_COMPRESSED: typing.Final[bytes] = b'MGZ1'
HEADER_ENCRYPTED: typing.Final[bytes] = b'MGE1'

# Size of crc32 checksum
CRC_SIZE: typing.Final[int] = 4

# Packing data struct
pack_struct = struct.Struct('<HHI')

# Helper functions
def fernet_key(crypt_key: bytes) -> str:
    """Generate key from password and seed

    Args:
        seed: Seed to use (normally header)

    Note: if password is not set, this will raise an exception
    """
    # Generate an URL-Safe base64 encoded 32 bytes key for Fernet
    # First, with seed + password, generate a 32 bytes key based on seed + password
    return base64.b64encode(hashlib.sha256(crypt_key).digest()).decode()


class _SerializableField(typing.Generic[T]):
    name: str
    type: typing.Type[T]
    default: DefaultValueType

    def __init__(self, type: typing.Type[T], default: DefaultValueType = UNASSIGNED):
        self.type = type
        self.default = default

    def _default(self) -> T:
        if isinstance(self.default, _Unassigned):
            return self.type()
        elif callable(self.default):
            return self.default()
        else:
            return self.default

    def __get__(
        self,
        instance: 'AutoSerializable',
        objtype: typing.Optional[typing.Type['AutoSerializable']] = None,
    ) -> T:
        """Get field value

        Arguments:
            instance {SerializableFields} -- Instance of class with field

        """
        if hasattr(instance, '_fields'):
            return getattr(instance, '_fields').get(self.name, self._default())
        if self.default is None:
            raise AttributeError(f"Field {self.name} is not set")
        return self._default()

    def __set__(self, instance: 'AutoSerializable', value: T) -> None:
        if not isinstance(value, self.type):
            raise TypeError(
                f"Field {self.name} cannot be set to {value} (type {self.type.__name__})"
            )
        if not hasattr(instance, '_fields'):
            setattr(instance, '_fields', {})
        getattr(instance, '_fields')[self.name] = value

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        """Basic marshalling of field

        Args:
            instance: Instance of class with field

        Returns:
            Marshalled field

        Note:
            Only str, int, and float are supported in this base class.
        """
        if self.type in (str, int, float):
            return str(self.__get__(instance)).encode()
        raise TypeError(f"Field {self.name} cannot be marshalled (type {self.type})")

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        """Basic unmarshalling of field

        Args:
            instance: Instance of class with field
            data: Marshalled field string

        Returns:
            None. The data is loaded into the field.

        Note:
            Only str, int, and float are supported in this base class.
        """
        if self.type in (str, int, float):
            tp: typing.Type = self.type
            self.__set__(instance, tp(data.decode()))
            return
        raise TypeError(f"Field {self.name} cannot be unmarshalled (type {self.type})")


# Integer field
class IntField(_SerializableField[int]):
    def __init__(self, default: int = 0):
        super().__init__(int, default)


class StringField(_SerializableField[str]):
    def __init__(self, default: str = ''):
        super().__init__(str, default)


class FloatField(_SerializableField[float]):
    def __init__(self, default: float = 0.0):
        super().__init__(float, default)

class BoolField(_SerializableField[bool]):
    def __init__(self, default: bool = False):
        super().__init__(bool, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        return b'1' if self.__get__(instance) else b'0'

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        self.__set__(instance, data == b'1')

class ListField(_SerializableField[typing.List]):
    """List field

    Note:
        All elements in the list must be serializable.
    """

    def __init__(
        self,
        default: typing.Union[
            typing.List, typing.Callable[[], typing.List]
        ] = lambda: [],
    ):
        super().__init__(list, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        return json.dumps(self.__get__(instance)).encode()

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        self.__set__(instance, json.loads(data))


class DictField(_SerializableField[typing.Dict]):
    """Dict field

    Note:
        All elements in the dict must be serializable.
    """

    def __init__(
        self,
        default: typing.Union[
            typing.Dict, typing.Callable[[], typing.Dict]
        ] = lambda: {},
    ):
        super().__init__(dict, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        return json.dumps(self.__get__(instance)).encode()

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        self.__set__(instance, json.loads(data))


class PasswordField(StringField):
    """Password field

    Note:
        The password is stored as a compressed string.
    """

    _crypt_key: str = ''

    def __init__(self, default: str = '', crypt_key: str = ''):
        super().__init__(default)
        self._crypt_key = crypt_key

    def _encrypt(self, value: str) -> bytes:
        """Encrypt a password

        Args:
            value: Password to encrypt

        Returns:
            Encrypted password
        """
        if self._crypt_key:
            # Generate a Fernet key from the password
            f = fernet.Fernet(fernet_key(self._crypt_key.encode()))
            return HEADER_ENCRYPTED + f.encrypt(value.encode())

        logger.warning("Password encryption is not enabled")
        return zlib.compress(value.encode())

    def _decrypt(self, value: bytes) -> bytes:
        """Decrypt a password

        Args:
            value: Password to decrypt

        Returns:
            Decrypted password
        """
        if self._crypt_key and value[: len(HEADER_ENCRYPTED)] == HEADER_ENCRYPTED:
            try:
                f = fernet.Fernet(fernet_key(self._crypt_key.encode()))
                return f.decrypt(value[len(HEADER_ENCRYPTED) :])
            except Exception:  # nosec: Defaults to zlib compression out of the exception
                pass  # returns the unencrypted password

        return zlib.decompress(value)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        return base64.b64encode(self._encrypt(self.__get__(instance)))

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        self.__set__(instance, self._decrypt(base64.b64decode(data)).decode())


# ************************
# * Serializable classes *
# ************************


class _FieldNameSetter(type):
    """Simply adds the name of the field in the class to the field object"""

    def __new__(cls, name, bases, attrs):
        fields = dict()
        for k, v in attrs.items():
            if isinstance(v, _SerializableField):
                v.name = k

        return super().__new__(cls, name, bases, attrs)


class AutoSerializable(metaclass=_FieldNameSetter):
    """This class allows the automatic serialization of fields in a class.

    Example:
        >>> class Test(SerializableFields):
        ...     a = IntField()
        ...     b = StrField()
        ...     c = FloatField()
        ...     d = ListField(defalut=lambda: [1, 2, 3])
    """

    _fields: typing.Dict[str, typing.Any]

    def process_data(self, header: bytes, data: bytes) -> bytes:
        """Process data before marshalling

        Args:
            data: Data to process

        Returns:
            Processed data

        Note:
            We provide header as a way of some constant value to be used in the
            processing. This is useful for encryption. (as salt, for example)
        """
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(header)))

        return data

    def unprocess_data(self, header: bytes, data: bytes) -> bytes:
        """Process data after unmarshalling

        Args:
            data: Data to process

        Returns:
            Processed data

        Note:
            We provide header as a way of some constant value to be used in the
            processing. This is useful for encryption. (as salt, for example)
        """
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(header)))

    @typing.final
    def marshal(self) -> bytes:
        # Iterate over own members and extract fields
        fields = {}
        for k, v in self.__class__.__dict__.items():
            if isinstance(v, _SerializableField):
                fields[v.name] = (str(v.__class__.__name__), v.marshal(self))

        # Serialized data is:
        # 2 bytes -> name length
        # 2 bytes -> type name length
        # 4 bytes -> data length
        # n bytes -> name
        # n bytes -> type name
        # n bytes -> data
        data = b''.join(
            pack_struct.pack(len(name.encode()), len(type_name.encode()), len(value))
            + name.encode()
            + type_name.encode()
            + value
            for name, (type_name, value) in fields.items()
        )

        # Calculate checksum
        checksum = zlib.crc32(data)
        # Compose header, that is V1_HEADER + checksum (4 bytes, big endian)
        header = HEADER_BASE + checksum.to_bytes(CRC_SIZE, 'big')
        # Return data processed with header
        return header + self.process_data(header, data)

    # final method, do not override
    @typing.final
    def unmarshal(self, data: bytes) -> None:
        # Check header
        if data[: len(HEADER_BASE)] != HEADER_BASE:
            raise ValueError('Invalid header')

        header = data[: len(HEADER_BASE) + CRC_SIZE]
        # Extract checksum
        checksum = int.from_bytes(
            header[len(HEADER_BASE) : len(HEADER_BASE) + 4], 'big'
        )
        # Unprocess data
        data = self.unprocess_data(header, data[len(header) :])

        # Check checksum
        if zlib.crc32(data) != checksum:
            raise ValueError('Invalid checksum')

        # Iterate over fields
        fields = {}
        while data:
            # Extract name length, type name length and data length
            name_len, type_name_len, data_len = pack_struct.unpack(data[:8])
            # Extract name, type name and data
            name, type_name, value = (
                data[8 : 8 + name_len].decode(),
                data[8 + name_len : 8 + name_len + type_name_len].decode(),
                data[
                    8
                    + name_len
                    + type_name_len : 8
                    + name_len
                    + type_name_len
                    + data_len
                ],
            )
            # Add to fields
            fields[name] = (type_name, value)
            # Remove from data
            data = data[8 + name_len + type_name_len + data_len :]

        for k, v in self.__class__.__dict__.items():
            if isinstance(v, _SerializableField):
                if v.name in fields and fields[v.name][0] == str(v.__class__.__name__):
                    v.unmarshal(self, fields[v.name][1])
                else:
                    if not v.name in fields:
                        logger.warning(f"Field {v.name} not found in unmarshalled data")
                    else:
                        logger.warning(
                            f"Field {v.name} has wrong type in unmarshalled data (should be {fields[v.name][0]} and is {v.__class__.name}"
                        )

    def __eq__(self, other: typing.Any) -> bool:
        """
        Basic equality check, checks if all _SerializableFields are equal
        """
        if not isinstance(other, AutoSerializable):
            return False

        for k, v in self.__class__.__dict__.items():
            if isinstance(v, _SerializableField):
                if getattr(self, k) != getattr(other, k):
                    return False

        return True

    def __str__(self) -> str:
        return ', '.join(
            [
                f"{k}={v.type.__name__}({v.__get__(self)})"
                for k, v in self.__class__.__dict__.items()
                if isinstance(v, _SerializableField)
            ]
        )


class AutoSerializableCompressed(AutoSerializable):
    """This class allows the automatic serialization of fields in a class compressed with zlib."""

    def process_data(self, header: bytes, data: bytes) -> bytes:
        return HEADER_COMPRESSED + zlib.compress(data)

    def unprocess_data(self, header: bytes, data: bytes) -> bytes:
        # if decompress fails, return data as is
        try:
            # Check header
            if data[: len(HEADER_COMPRESSED)] != HEADER_COMPRESSED:
                raise Exception()  # Returns data as is
            return zlib.decompress(data[len(HEADER_COMPRESSED) :])
        except Exception:
            return super().unprocess_data(header, data)


class AutoSerializableEncrypted(AutoSerializable):
    """This class allows the automatic serialization of fields in a class encrypted with AES."""

    # Common key for all instances
    _crypt_key: typing.ClassVar[str] = settings.SECRET_KEY[:16]

    def key(self, seed: bytes) -> str:
        """Generate key from password and seed

        Args:
            seed: Seed to use (normally header)

        Note: if password is not set, this will raise an exception
        """
        if not self._crypt_key:
            raise ValueError('Password not set')

        return fernet_key(seed + (self._crypt_key.encode()))

    def process_data(self, header: bytes, data: bytes) -> bytes:
        f = fernet.Fernet(self.key(header))
        return HEADER_ENCRYPTED + f.encrypt(data)

    def unprocess_data(self, header: bytes, data: bytes) -> bytes:
        # if decrypt fails, return data as is
        try:
            # Check if data is encrypted
            if data[: len(HEADER_ENCRYPTED)] != HEADER_ENCRYPTED:
                return super().unprocess_data(header, data)
            f = fernet.Fernet(self.key(header))
            return f.decrypt(data[len(HEADER_ENCRYPTED) :])
        except fernet.InvalidToken:
            return super().unprocess_data(header, data)

    @staticmethod
    def set_crypt_key(crypt_key: str) -> None:
        """Set the password for all instances of this class.

        Args:
            password: Password to set

        Note:
            On Django, this should be set preferably in settings.py,
            so all instances of this class will use the same password from the start.
        """
        AutoSerializableEncrypted._crypt_key = crypt_key[:16]
