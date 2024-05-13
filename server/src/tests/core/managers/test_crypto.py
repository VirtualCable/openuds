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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import collections.abc
import datetime
import uuid as uuid_type

from django.conf import settings

from uds.core.managers import crypto
from ...utils.test import UDSTestCase

TEST_STRING = 'abcdefghijklπερισσότεροήλιγότερομεγάλοκείμενογιαχαρακτήρεςmnopqrstuvwxyz或多或少的字符长文本ABCD'
CRYPTED_STRING = (
    b'H\x85\xedtL\xca6\x8cmv4D\x1b\xbe-/4\xfc\xa8\xe9\x08\x96\x9dON\x7f\x94'
    b'\x11`\x91(0JkC\xd6\xab\xe4\x95\xe3\x84\xd3\xd4\x10\xdeJm\x17\xb7O\x10T'
    b'\xc9"j{\xf3\xc5\xa5\xd1R\xc5\x0c\xe4!_\x03\x1elQ2\x8d3\x17\r\x84\xc0>'
    b'\x92z2.\xf81=\xed\xf6z\xc6\x057\xe1\xb8\x7f\xc6\xc2\x14>\x10\xa4\xec\x85'
    b'3pdux\xbbB\xc8\xe7\x8f\x96\xc3\x9f\x07\xaa\x13\xf1\x0c\x7f\xf2\xe0d\x99'
    b'\x12\xc6s\xa5\xd9^\xd2\xbb|=\x93=\xfb\xab>w\x04\x9cti\xb9\xcf@\\\xd5\x1c'
    b'\xd9\x90\x04Y\x82 \xb5\xa2\xf1'    
)

UDSK = crypto.UDSK  # Store original UDSK

class CryptoManagerTest(UDSTestCase):
    manager = crypto.CryptoManager()
    _oldUDSK: bytes

    def setUp(self) -> None:
        # Override UDSK
        crypto.UDSK = b'1234567890123456'  # type: ignore  # UDSK is final, 
        return super().setUp()
    
    def tearDown(self) -> None:
        crypto.UDSK = UDSK  # type: ignore  # UDSK is final,
        return super().tearDown()

    def test_RSA(self) -> None:
        testStr = 'Test string'
        cryptStr = self.manager.encrypt(testStr)

        self.assertIsInstance(cryptStr, str, 'Crypted string is not unicode')

        decryptStr = self.manager.decrypt(cryptStr)

        self.assertIsInstance(decryptStr, str, 'Decrypted string is not unicode')
        self.assertEqual(
            decryptStr,
            testStr,
            'Decrypted test string failed!: {} vs {}'.format(decryptStr, testStr),
        )

    def test_Xor(self) -> None:
        testStr1a = 'Test String more or less with strange chars €@"áéöüìùòàäñÑ@æßðđŋħ←↓→þøŧ¶€ł@łĸµn”“«»“”nµłĸŋđðßææ@ł€¶ŧ←↓→øþ'
        testStr1b = 'Test String 2 with some ł€¶ŧ←↓→øþ'

        testStr2a = 'xor string chasquera'
        testStr2b = 'xor string chasquera #~½¬æßð'

        for s1 in (testStr1a, testStr1b):
            for s2 in (testStr2a, testStr2b):
                xor = self.manager.xor(s1, s2)
                self.assertIsInstance(xor, bytes, 'Returned xor string is not bytes')
                xorxor = self.manager.xor(xor, s2)
                self.assertEqual(xorxor.decode('utf-8'), s1)

    def test_Symcrypt(self) -> None:
        testStr1a = 'Test String more or less with strange chars €@"áéöüìùòàäñÑ@æßðđŋħ←↓→þøŧ¶€ł@łĸµn”“«»“”nµłĸŋđðßææ@ł€¶ŧ←↓→øþ'
        testStr1b = 'Test String 2 with some ł€¶ŧ←↓→øþ'

        testStr2a = 'xor string chasquera'
        testStr2b = 'xor string chasquera #~½¬æßð'

        for s1 in (testStr1a, testStr1b):
            for s2 in (testStr2a, testStr2b):
                sym = self.manager.symmetric_encrypt(s1, s2)
                self.assertIsInstance(sym, bytes, 'Returned xor string is not bytes')
                symd = self.manager.symmetric_decrypt(sym, s2)
                self.assertEqual(symd, s1)

    def test_Certs(self) -> None:
        # Right now, only tests that these methods do not fails
        self.manager.load_private_key(settings.RSA_KEY)

        self.manager.load_certificate(settings.CERTIFICATE)
        self.manager.load_certificate(settings.CERTIFICATE.encode('utf8'))

    def test_Hash(self) -> None:
        testStr = 'Test String for hash'
        # knownHashValue = '4e1311c1378993b34430988f4836b8e6b8beb219'

        for _ in (testStr, testStr.encode('utf-8')):
            hashValue = self.manager.hash(testStr)
            self.assertIsInstance(hashValue, str, 'Returned hash must be an string')

    def test_Uuid(self) -> None:
        uuid = self.manager.uuid()
        # Ensure is an string
        self.assertIsInstance(uuid, str)
        # Ensure is lowercase
        self.assertEqual(uuid, uuid.lower())
        # Ensure is a valid uuid
        uuid_type.UUID(uuid)

        for o in (
            (1, '47c69004-5f4c-5266-b93d-747b318e2d3f'),
            (1.1, 'dfdae060-00a9-5e8d-9a28-3b77b8af18eb'),
            ('Test String', 'dce56818-2231-5d0f-abd3-73b3b8c1c7ee'),
            (
                datetime.datetime(2014, 9, 15, 17, 2, 12),
                'a42521d7-2b2f-5767-992c-482aef05b25c',
            ),
        ):
            uuid = self.manager.uuid(o[0])
            self.assertIsInstance(uuid, str, 'Returned uuid must be an string')
            self.assertEqual(uuid, o[1])
            # Ensure is lowercase
            self.assertEqual(uuid, uuid.lower())
            # Ensure is a valid uuid
            uuid_type.UUID(uuid)

    def testFastCrypt(self) -> None:
        # Fast crypt uses random padding text, so the last block can be different
        self.assertEqual(
            self.manager.fast_crypt(TEST_STRING.encode())[:-16], CRYPTED_STRING[:-16]
        )

    def testFastDecrypt(self) -> None:
        self.assertEqual(self.manager.fast_decrypt(CRYPTED_STRING).decode(), TEST_STRING)
