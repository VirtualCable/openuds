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
import collections.abc
import dataclasses
import typing

from uds.core.util import autoserializable

from ...utils.test import UDSTestCase

UNICODE_CHARS = 'ñöçóá^(pípè)'
UNICODE_CHARS_2 = 'ñöçóá^(€íöè)'


@dataclasses.dataclass
class SerializableDataclass:
    int_val: int = 0
    str_val: str = ''
    float_val: float = 0.0


class SerializableNamedTuple(typing.NamedTuple):
    int_val: int = 0
    str_val: str = ''
    float_val: float = 0.0


class AutoSerializableClass(autoserializable.AutoSerializable):
    int_field = autoserializable.IntegerField(default=11)
    str_field = autoserializable.StringField(default='str')
    float_field = autoserializable.FloatField(default=44.0)
    bool_field = autoserializable.BoolField(default=False)
    password_field = autoserializable.PasswordField(default='password')  # nosec: test password
    list_field = autoserializable.ListField[int](default=lambda: [1, 2, 3])
    dict_field = autoserializable.DictField[str, int](default=lambda: {'a': 1, 'b': 2, 'c': 3})
    obj_dc_field = autoserializable.ObjectField[SerializableDataclass](
        SerializableDataclass, default=lambda: SerializableDataclass(1, '2', 3.0)
    )
    obj_nt_field = autoserializable.ObjectField[SerializableNamedTuple](
        SerializableNamedTuple, default=lambda: SerializableNamedTuple(1, '2', 3.0)
    )

    non_auto_int = 1


class AutoSerializableCompressedClass(autoserializable.AutoSerializableCompressed):
    int_field = autoserializable.IntegerField()
    str_field = autoserializable.StringField()
    float_field = autoserializable.FloatField()
    bool_field = autoserializable.BoolField()
    password_field = autoserializable.PasswordField()
    list_field = autoserializable.ListField[int]()
    dict_field = autoserializable.DictField[str, int]()
    obj_dc_field = autoserializable.ObjectField[SerializableDataclass](SerializableDataclass)
    obj_nt_field = autoserializable.ObjectField[SerializableNamedTuple](SerializableNamedTuple)

    non_auto_int = 1


class AutoSerializableEncryptedClass(autoserializable.AutoSerializableEncrypted):
    int_field = autoserializable.IntegerField()
    str_field = autoserializable.StringField()
    float_field = autoserializable.FloatField()
    bool_field = autoserializable.BoolField()
    password_field = autoserializable.PasswordField()
    list_field = autoserializable.ListField[int]()
    dict_field = autoserializable.DictField[str, int]()
    obj_dc_field = autoserializable.ObjectField[SerializableDataclass](SerializableDataclass)
    obj_nt_field = autoserializable.ObjectField[SerializableNamedTuple](SerializableNamedTuple)

    non_auto_int = 1


class AddedClass:
    tr1: int = 0
    tr2: str = 'tr2'


class DerivedAutoSerializableClass(AutoSerializableClass):
    int_field2 = autoserializable.IntegerField()
    str_field2 = autoserializable.StringField()


class DerivedAutoSerializableClass2(AddedClass, AutoSerializableClass):
    int_field2 = autoserializable.IntegerField()
    str_field2 = autoserializable.StringField()


class AutoSerializableClassWithMissingFields(autoserializable.AutoSerializable):
    int_field = autoserializable.IntegerField()
    bool_field = autoserializable.BoolField()
    password_field = autoserializable.PasswordField()
    list_field = autoserializable.ListField[int]()
    obj_nt_field = autoserializable.ObjectField[SerializableNamedTuple](SerializableNamedTuple)

    non_auto_int = 1


class AutoSerializable(UDSTestCase):
    def basic_check(
        self,
        cls1: type['AutoSerializableClass|AutoSerializableCompressedClass|AutoSerializableEncryptedClass'],
        cls2: type['AutoSerializableClass|AutoSerializableCompressedClass|AutoSerializableEncryptedClass'],
    ) -> None:
        # Test basic serialization
        a = cls1()
        a.int_field = 1
        a.str_field = UNICODE_CHARS
        a.float_field = 3.0
        a.bool_field = True
        a.password_field = UNICODE_CHARS_2  # nosec: test password
        a.list_field = [1, 2, 3]
        a.dict_field = {'a': 1, 'b': 2, 'c': 3}
        a.obj_dc_field = SerializableDataclass(1, '2', 3.0)
        a.obj_nt_field = SerializableNamedTuple(1, '2', 3.0)

        a.non_auto_int = 2

        data = a.marshal()

        b = cls2()
        b.non_auto_int = 111
        b.unmarshal(data)

        self.assertEqual(a, b)  # Non auto fields are not compared

        for i in (a, b):
            self.assertEqual(i.int_field, 1)
            self.assertEqual(i.str_field, UNICODE_CHARS)
            self.assertEqual(i.float_field, 3.0)
            self.assertEqual(i.bool_field, True)
            self.assertEqual(i.password_field, UNICODE_CHARS_2)
            self.assertEqual(i.list_field, [1, 2, 3])
            self.assertEqual(i.dict_field, {'a': 1, 'b': 2, 'c': 3})
            self.assertEqual(i.obj_dc_field, SerializableDataclass(1, '2', 3.0))
            self.assertEqual(i.obj_nt_field, SerializableNamedTuple(1, '2', 3.0))

        self.assertEqual(a.non_auto_int, 2)  # Not altered by serialization

        self.assertEqual(b.non_auto_int, 111)  # Not altered by deserialization

    def test_auto_serializable_base(self) -> None:
        self.basic_check(AutoSerializableClass, AutoSerializableClass)

    def test_auto_serializable_compressed(self) -> None:
        self.basic_check(AutoSerializableCompressedClass, AutoSerializableCompressedClass)

    def test_auto_serializable_encrypted(self) -> None:
        self.basic_check(AutoSerializableEncryptedClass, AutoSerializableEncryptedClass)

    def test_auto_serializable_base_compressed(self) -> None:
        self.basic_check(AutoSerializableClass, AutoSerializableCompressedClass)

    def test_auto_serializable_base_encrypted(self) -> None:
        self.basic_check(AutoSerializableClass, AutoSerializableEncryptedClass)

    def test_auto_serializable_derived(self):
        instance = DerivedAutoSerializableClass()
        instance.int_field = 1
        instance.str_field = UNICODE_CHARS
        instance.float_field = 3.0
        instance.bool_field = True
        instance.password_field = UNICODE_CHARS_2
        instance.list_field = [1, 2, 3]
        instance.dict_field = {'a': 1, 'b': 2, 'c': 3}
        instance.int_field2 = 2
        instance.str_field2 = UNICODE_CHARS_2

        data = instance.marshal()

        instance2 = DerivedAutoSerializableClass()
        instance2.unmarshal(data)

        self.assertEqual(instance, instance2)

    def test_auto_serializable_derived_added(self):
        instance = DerivedAutoSerializableClass2()
        instance.int_field = 1
        instance.str_field = UNICODE_CHARS
        instance.float_field = 3.0
        instance.bool_field = True
        instance.password_field = UNICODE_CHARS_2
        instance.list_field = [1, 2, 3]
        instance.dict_field = {'a': 1, 'b': 2, 'c': 3}
        instance.int_field2 = 2
        instance.str_field2 = UNICODE_CHARS_2
        instance.tr1 = 3
        instance.tr2 = UNICODE_CHARS

        data = instance.marshal()

        instance2 = DerivedAutoSerializableClass2()
        instance2.unmarshal(data)

        self.assertEqual(instance, instance2)

    def test_auto_serializable_with_missing_fields(self):
        instance = AutoSerializableClass()
        instance.int_field = 1
        instance.str_field = UNICODE_CHARS
        instance.float_field = 3.0
        instance.bool_field = True
        instance.password_field = UNICODE_CHARS_2  # nosec: test password
        instance.list_field = [1, 2, 3]
        instance.dict_field = {'a': 1, 'b': 2, 'c': 3}
        instance.obj_dc_field = SerializableDataclass(1, '2', 3.0)
        instance.obj_nt_field = SerializableNamedTuple(2, '3', 4.0)

        data = instance.marshal()

        instance2 = AutoSerializableClassWithMissingFields()
        instance2.unmarshal(data)

        self.assertNotEqual(instance2, instance)  # Missing fields, so not equal

        self.assertEqual(instance2.int_field, 1)
        self.assertEqual(instance2.bool_field, True)
        self.assertEqual(instance2.password_field, UNICODE_CHARS_2)
        self.assertEqual(instance2.list_field, [1, 2, 3])
        self.assertEqual(instance2.obj_nt_field, SerializableNamedTuple(2, '3', 4.0))

    def test_auto_serializable_with_added_fields(self):
        instance = AutoSerializableClassWithMissingFields()
        instance.int_field = 1
        instance.bool_field = True
        instance.password_field = UNICODE_CHARS_2  # nosec: test password
        instance.list_field = [1, 2, 3]
        instance.obj_nt_field = SerializableNamedTuple(2, '3', 4.0)

        data = instance.marshal()

        instance2 = AutoSerializableClass()
        # Overwrite defaults, so we can check that they are restored on unmarshal
        instance2.str_field = UNICODE_CHARS
        instance2.float_field = 3.0
        instance2.dict_field = {'a': 11, 'b': 22, 'c': 33}
        instance2.obj_dc_field = SerializableDataclass(11, '22', 33.0)
        
        instance2.unmarshal(data)

        self.assertNotEqual(instance2, instance)

        # Ensure that missing fields are set to default values
        # and deserialize correctly the rest of the fields
        self.assertEqual(instance2.int_field, 1)  # deserialized value
        self.assertEqual(instance2.str_field, 'str')  # default value
        self.assertEqual(instance2.float_field, 44.0)  # default value
        self.assertEqual(instance2.bool_field, True)  # deserialized value
        self.assertEqual(instance2.password_field, UNICODE_CHARS_2)  # deserialized value
        self.assertEqual(instance2.list_field, [1, 2, 3])  # deserialized value
        self.assertEqual(instance2.dict_field, {'a': 1, 'b': 2, 'c': 3})  # default value
        self.assertEqual(instance2.obj_dc_field, SerializableDataclass(1, '2', 3.0))  # default value
        self.assertEqual(instance2.obj_nt_field, SerializableNamedTuple(2, '3', 4.0))  # deserialized value
