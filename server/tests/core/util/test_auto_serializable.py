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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# We use commit/rollback
import typing
import collections.abc

from ...utils.test import UDSTestCase
from uds.core.util import auto_serializable

UNICODE_CHARS = 'ñöçóá^(pípè)'
UNICODE_CHARS_2 = 'ñöçóá^(€íöè)'


class AutoSerializableClass(auto_serializable.AutoSerializable):
    int_field = auto_serializable.IntegerField()
    str_field = auto_serializable.StringField()
    float_field = auto_serializable.FloatField()
    bool_field = auto_serializable.BoolField()
    password_field = auto_serializable.PasswordField()
    list_field = auto_serializable.ListField[int]()
    dict_field = auto_serializable.DictField()

    non_auto_int = 1


class AutoSerializableCompressedClass(auto_serializable.AutoSerializableCompressed):
    int_field = auto_serializable.IntegerField()
    str_field = auto_serializable.StringField()
    float_field = auto_serializable.FloatField()
    bool_field = auto_serializable.BoolField()
    password_field = auto_serializable.PasswordField()
    list_field = auto_serializable.ListField[int]()
    dict_field = auto_serializable.DictField()

    non_auto_int = 1


class AutoSerializableEncryptedClass(auto_serializable.AutoSerializableEncrypted):
    int_field = auto_serializable.IntegerField()
    str_field = auto_serializable.StringField()
    float_field = auto_serializable.FloatField()
    bool_field = auto_serializable.BoolField()
    password_field = auto_serializable.PasswordField()
    list_field = auto_serializable.ListField[int]()
    dict_field = auto_serializable.DictField()

    non_auto_int = 1

class AddedClass:
    tr1: int = 0
    tr2: str = 'tr2'

class DerivedAutoSerializableClass(AutoSerializableClass):
    int_field2 = auto_serializable.IntegerField()
    str_field2 = auto_serializable.StringField()
    
class DerivedAutoSerializableClass2(AddedClass, AutoSerializableClass):
    int_field2 = auto_serializable.IntegerField()
    str_field2 = auto_serializable.StringField()


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
        
        self.assertEqual(a.non_auto_int, 2)    # Not altered by serialization
        
        self.assertEqual(b.non_auto_int, 111)  # Not altered by deserialization
        


    def test_auto_serializable_base(self):
        self.basic_check(AutoSerializableClass, AutoSerializableClass)

    def test_auto_serializable_compressed(self):
        self.basic_check(AutoSerializableCompressedClass, AutoSerializableCompressedClass)

    def test_auto_serializable_encrypted(self):
        self.basic_check(AutoSerializableEncryptedClass, AutoSerializableEncryptedClass)

    def test_auto_serializable_base_compressed(self):
        self.basic_check(AutoSerializableClass, AutoSerializableCompressedClass)

    def test_auto_serializable_base_encrypted(self):
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