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

Implements de AutoSerializable class, that allows to serialize/deserialize in a simple way
This class in incompatible with UserInterface derived classes, as it metaclass is not compatible

To use it, simple place it as first parent class, and follow by the rest of the classes to inherit from

Example: 
from uds.core.util import AutoSerializable
from uds.core import services

class UserDeploymentService(AutoSerializable, services.UserDeployment):
    ...

"""

import dataclasses
import itertools
import typing
import collections.abc
import logging
import json
import zlib
import base64
import hashlib
import struct
import abc

from cryptography import fernet

from django.conf import settings

from uds.core.serializable import Serializable


# pylint: disable=too-few-public-methods
class _Unassigned:
    pass


# means field has no default value
UNASSIGNED = _Unassigned()

T = typing.TypeVar('T')
V = typing.TypeVar('V')

DefaultValueType = typing.Union[T, collections.abc.Callable[[], T], _Unassigned]

logger = logging.getLogger(__name__)

# Constants

# Headers for the serialized data
# A header is composed of:
# 6 bytes -> Header, where last byte is the version (1..9 for now, a..z can be also used in the future)
HEADER_BASE: typing.Final[bytes] = b'MGBAS1'
HEADER_COMPRESSED: typing.Final[bytes] = b'MGZAS1'
HEADER_ENCRYPTED: typing.Final[bytes] = b'MGEAS1'

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
    return base64.b64encode(hashlib.sha256(crypt_key).digest()).decode()


# checker for autoserializable data
def is_autoserializable_data(data: bytes) -> bool:
    """Check if data is is from an autoserializable class

    Args:
        data: Data to check

    Returns:
        True if data is autoserializable, False otherwise
    """
    return data[: len(HEADER_BASE)] == HEADER_BASE


@dataclasses.dataclass(slots=True)
class _MarshalInfo:
    name: str
    type_name: str
    value: bytes

    def marshal(self) -> bytes:
        """Field data marshalling"""
        return (
            pack_struct.pack(len(self.name.encode()), len(self.type_name.encode()), len(self.value))
            + self.name.encode()
            + self.type_name.encode()
            + self.value
        )

    @staticmethod
    def unmarshal(data: bytes) -> typing.Tuple['_MarshalInfo', bytes]:
        """Field data unmarshalling

            # Serialized data is:
            # 2 bytes -> name length
            # 2 bytes -> type name length
            # 4 bytes -> data length
            # n bytes -> name
            # n bytes -> type name
            # n bytes -> data

        Args:
            data: Data to unmarshal

        Returns:
            unmarshalled field and remaining data
            
        """
        # Extract name length, type name length and data length
        name_len, type_name_len, data_len = pack_struct.unpack(data[:8])
        # Extract name, type name and data
        name, type_name, value = (
            data[8 : 8 + name_len].decode(),
            data[8 + name_len : 8 + name_len + type_name_len].decode(),
            data[8 + name_len + type_name_len : 8 + name_len + type_name_len + data_len],
        )
        # Return field and remaining data
        return (
            _MarshalInfo(name, type_name, value),
            data[8 + name_len + type_name_len + data_len :],
        )


# pylint: disable=unnecessary-dunder-call
class _SerializableField(typing.Generic[T]):
    name: str
    obj_type: 'type[T]'
    default: DefaultValueType[T]

    def __init__(self, obj_type: 'type[T]', default: DefaultValueType[T] = UNASSIGNED):
        self.obj_type = obj_type
        self.default = default

    def _default(self) -> T:
        if isinstance(self.default, _Unassigned):
            return self.obj_type()
        if callable(self.default):
            return self.default()
        return self.default

    def __get__(
        self,
        instance: 'AutoSerializable',
        objtype: typing.Optional['type[AutoSerializable]'] = None,
    ) -> T:
        """Get field value

        Arguments:
            instance {SerializableFields} -- Instance of class with field

        """
        if hasattr(instance, '_fields'):
            return getattr(instance, '_fields').get(self.name, self._default())
        if self.default is None:
            raise AttributeError(f"Field {self.name} is not set")
        # Set default using setter
        self.__set__(instance, self._default())
        return getattr(instance, '_fields')[self.name]

    def __set__(self, instance: 'AutoSerializable', value: T) -> None:
        # If type is float and value is int, convert it
        # Or if type is int and value is float, convert it
        if typing.cast(typing.Type[typing.Any], self.obj_type) in (float, int) and isinstance(
            value, (float, int)
        ):
            value = self.obj_type(value)  # type: ignore
        if not isinstance(value, self.obj_type):
            # Try casting to load values (maybe a namedtuple, i.e.)
            try:
                if isinstance(value, collections.abc.Mapping):
                    value = self.obj_type(**value)  # If a dict, try to cast it to the object
                elif isinstance(value, collections.abc.Iterable):  # IF a list, tuple, etc... try to cast it
                    value = self.obj_type(*value)
                else:  # Maybe it has a constructor that accepts a single value or is a callable...
                    value = typing.cast(typing.Callable[..., typing.Any], self.obj_type)(value)
            except Exception:
                # Allow int to float conversion and viceversa
                raise TypeError(f"Field {self.name} cannot be set to {value} (type {self.obj_type.__name__})")
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
        if typing.cast(typing.Type[typing.Any], self.obj_type) in (str, int, float):
            return str(self.__get__(instance)).encode()
        raise TypeError(f"Field {self.name} cannot be marshalled (type {self.obj_type})")

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
        if typing.cast(typing.Type[typing.Any], self.obj_type) in (str, int, float):
            tp: typing.Type[T] = self.obj_type
            self.__set__(instance, tp(data.decode()))  # type: ignore  # mypy complains about calling tp(...)
            return
        raise TypeError(f"Field {self.name} cannot be unmarshalled (type {self.obj_type})")


# Integer field
class IntegerField(_SerializableField[int]):
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
        return b'\xff' if self.__get__(instance) else b'\x00'

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        self.__set__(instance, data != b'\x00')


class ListField(_SerializableField[list[T]], list[T]):
    """List field

    Note:
        All elements in the list must be serializable in JSON, but can be of different types.
    """

    def __init__(
        self,
        default: typing.Union[list[T], collections.abc.Callable[[], list[T]]] = lambda: [],
    ):
        super().__init__(list, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        # \x01 is the version of this field marshal format, so we can change it in the future
        return b'\x01' + json.dumps(self.__get__(instance)).encode()

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        if data[0] != 1:
            raise ValueError('Invalid list data')
        self.__set__(instance, json.loads(data[1:]))


class DictField(_SerializableField[dict[T, V]], dict[T, V]):
    """Dict field

    Note:
        All elements in the dict must be serializable.
    """

    def __init__(
        self,
        default: typing.Union[dict[T, V], collections.abc.Callable[[], dict[T, V]]] = lambda: {},
    ):
        super().__init__(dict, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        # \x01 is the version of this field marshal format, so we can change it in the future
        return b'\x01' + json.dumps(self.__get__(instance)).encode()

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        if data[0] != 1:
            raise ValueError('Invalid dict data')
        self.__set__(instance, json.loads(data[1:]))


class ObjectField(_SerializableField[T]):
    """Object field

    Note:
        Object type must be serializable.
        Also, take care with these fields and their changes, they are serialized as JSON
        Perfectly supported classes are dataclasses and namedtuples, but any serializable class
        can be used.

        Again, be advised with using objects and later changing their definition, as this can
        lead to errors when unmarshalling data.

    """

    def __init__(self, obj_type: 'type[T]', default: DefaultValueType[T] = UNASSIGNED):
        super().__init__(obj_type, default)

    def marshal(self, instance: 'AutoSerializable') -> bytes:
        # if is a dataclass
        value = typing.cast(typing.Any, self.__get__(instance))
        if dataclasses.is_dataclass(self.obj_type):
            to_marshal = dataclasses.asdict(value)
        elif hasattr(value, '_asdict'):
            to_marshal = value._asdict()  # Serialize namedtuples as dicts
        else:
            to_marshal = value

        return b'\x01' + json.dumps(to_marshal).encode()

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        if data[0] != 1:
            raise ValueError('Invalid object data')
        self.__set__(instance, json.loads(data[1:]))


class PasswordField(StringField):
    """Password field

    Note:
        The password is stored as a compressed string.
    """

    _crypt_key: str = ''

    def __init__(self, default: str = '', crypt_key: str = ''):
        super().__init__(default)
        self._crypt_key = crypt_key or settings.SECRET_KEY[:32]  # If no SECRET_KEY, will raise an exception...

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
        # \x01 is the version of this field marshal format, so we can change it in the future
        return b'\x01' + base64.b64encode(self._encrypt(self.__get__(instance)))

    def unmarshal(self, instance: 'AutoSerializable', data: bytes) -> None:
        if data[:1] != b'\x01':
            raise ValueError('Invalid password data')
        self.__set__(instance, self._decrypt(base64.b64decode(data[1:])).decode())


# ************************
# * Serializable classes *
# ************************


class _FieldNameSetter(abc.ABCMeta, type):
    """Simply adds the name of the field in the class to the field object"""

    def __new__(mcs, name: str, bases: typing.Tuple[type, ...], attrs: dict[str, typing.Any]) -> type:
        for k, v in attrs.items():
            if isinstance(v, _SerializableField):
                v.name = k

        return super().__new__(mcs, name, bases, attrs)


class AutoSerializable(Serializable, metaclass=_FieldNameSetter):
    """This class allows the automatic serialization of fields in a class.

    Example:
        >>> class Test(SerializableFields):
        ...     a = IntegerField()
        ...     b = StrField()
        ...     c = FloatField()
        ...     d = ListField(defalut=lambda: [1, 2, 3])
    """

    _fields: dict[str, typing.Any]

    def _autoserializable_fields(self) -> collections.abc.Iterator[tuple[str, _SerializableField[typing.Any]]]:
        """Returns an iterator over all fields in the class, including inherited ones

        Returns:
            Tuple(name, field) for each field in the class and its bases
        """
        cls = self.__class__
        while True:
            for k, v in cls.__dict__.items():
                if isinstance(v, _SerializableField):
                    yield k, v
            for c in cls.__bases__:
                if issubclass(c, AutoSerializable) and c != AutoSerializable:
                    cls = c
                    break
            else:
                break  # No more bases

    def process_data(self, header: bytes, data: bytes) -> bytes:
        """Process data before marshalling

        Args:
            data: Data to process

        Returns:
            Processed data (basycally xor with header cyclically)

        Note:
            process is used so we can, for example, encrypt data
            or compress then (as in derived classes)
        """
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(header)))

    def unprocess_data(self, header: bytes, data: bytes) -> bytes:
        """Process data after unmarshalling

        Args:
            data: Data to process

        Returns:
            Processed data (basycally xor with header cyclically)

        Note:
            unprocess is used so we can, for example, unencrypt data
            or uncompress then (as in derived classes)
        """
        return bytes(a ^ b for a, b in zip(data, itertools.cycle(header)))

    def marshal(self) -> bytes:
        # Iterate over own members and extract fields
        fields: list[_MarshalInfo] = [
            _MarshalInfo(name=v.name, type_name=str(v.__class__.__name__), value=v.marshal(self))
            for _, v in self._autoserializable_fields()
        ]

        # Serialized data is:
        # 2 bytes -> name length
        # 2 bytes -> type name length
        # 4 bytes -> data length
        # n bytes -> name
        # n bytes -> type name
        # n bytes -> data
        data = b''.join(field.marshal() for field in fields)

        # Calculate checksum
        checksum = zlib.crc32(data)
        # Compose header, that is V1_HEADER + checksum (4 bytes, big endian)
        header = HEADER_BASE + checksum.to_bytes(CRC_SIZE, 'big')
        # Return data processed with header
        return header + self.process_data(header, data)

    # Only override this for checking if data is valid
    # and, alternatively, retrieve it from a different source
    def unmarshal(self, data: bytes) -> None:
        # Check header
        if data[: len(HEADER_BASE)] != HEADER_BASE:
            raise ValueError('Invalid header')

        header = data[: len(HEADER_BASE) + CRC_SIZE]
        # Extract checksum
        checksum = int.from_bytes(header[len(HEADER_BASE) : len(HEADER_BASE) + 4], 'big')
        # Unprocess data
        data = self.unprocess_data(header, data[len(header) :])

        # Check checksum
        if zlib.crc32(data) != checksum:
            raise ValueError('Invalid checksum')

        # Iterate over fields
        fields: dict[str, _MarshalInfo] = {}
        while data:
            field, data = _MarshalInfo.unmarshal(data)
            fields[field.name] = field

        for _, v in self._autoserializable_fields():
            if v.name in fields:
                if fields[v.name].type_name == str(v.__class__.__name__):
                    v.unmarshal(self, fields[v.name].value)
                else:
                    logger.warning(
                        'Field %s has wrong type in unmarshalled data (should be %s and is %s',
                        v.name,
                        fields[v.name].type_name,
                        v.__class__.__name__,
                    )
            else:
                logger.debug('Field %s not found in unmarshalled data', v.name)
                v.__set__(self, v._default())  # Set default value

    def __eq__(self, other: typing.Any) -> bool:
        """
        Basic equality check, checks if all _SerializableFields are equal

        note: NON _SerializableFields are not checked!!
        """
        if not isinstance(other, AutoSerializable):
            return False

        all_fields_attrs = list(self._autoserializable_fields())

        if {k for k, _ in all_fields_attrs} != {k for k, _ in other._autoserializable_fields()}:
            return False

        for k, _ in all_fields_attrs:
            if getattr(self, k) != getattr(other, k):
                return False

        return True

    def __str__(self) -> str:
        return ', '.join(
            [f"{k}={v.obj_type.__name__}({v.__get__(self)})" for k, v in self._autoserializable_fields()]
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
            seed: Seed to use (normally header, that is outside the encription and is variable, acting as a salt)

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
