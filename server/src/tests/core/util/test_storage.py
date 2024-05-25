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
"""

import base64
from ...utils.test import UDSTestCase
from uds.core.util import storage
from uds import models

UNICODE_CHARS = 'ñöçóá^(pípè)'
UNICODE_CHARS_2 = 'ñöçóá^(€íöè)'
VALUE_1 = ['unicode', b'string', {'a': 1, 'b': 2.0}]


class StorageTest(UDSTestCase):
    def test_storage(self) -> None:
        strg = storage.Storage(UNICODE_CHARS)

        strg.put(UNICODE_CHARS, b'chars')
        strg.save_to_db('saveData', UNICODE_CHARS, UNICODE_CHARS)
        strg.save_to_db('saveData2', UNICODE_CHARS_2, UNICODE_CHARS)
        strg.save_to_db('saveData3', UNICODE_CHARS, 'attribute')
        strg.save_to_db('saveData4', UNICODE_CHARS_2, 'attribute')
        strg.put(b'key', UNICODE_CHARS)
        strg.put(UNICODE_CHARS_2, UNICODE_CHARS)

        strg.save_pickled('pickle', VALUE_1)

        self.assertEqual(strg.read(UNICODE_CHARS), u'chars')  # Always returns unicod
        self.assertEqual(strg.read_from_db('saveData'), UNICODE_CHARS)
        self.assertEqual(strg.read_from_db('saveData2'), UNICODE_CHARS_2)
        self.assertEqual(strg.read(b'key'), UNICODE_CHARS)
        self.assertEqual(strg.read(UNICODE_CHARS_2), UNICODE_CHARS)
        self.assertEqual(strg.read_pickled('pickle'), VALUE_1)

        self.assertEqual(len(list(strg.search_by_attr1(UNICODE_CHARS))), 2)
        self.assertEqual(len(list(strg.search_by_attr1('attribute'))), 2)

        strg.remove(UNICODE_CHARS)
        strg.remove(b'key')
        strg.remove('pickle')

        self.assertIsNone(strg.read(UNICODE_CHARS))
        self.assertIsNone(strg.read(b'key'))
        self.assertIsNone(strg.read_pickled('pickle'))

    def test_storage_as_dict(self) -> None:
        strg = storage.Storage(UNICODE_CHARS)

        strg.put(UNICODE_CHARS, 'chars')

        with strg.as_dict() as d:
            d['test_key'] = UNICODE_CHARS_2

            # Assert that UNICODE_CHARS is in the dict
            self.assertEqual(d[UNICODE_CHARS], 'chars')

            self.assertEqual(d['test_key'], UNICODE_CHARS_2)
            
            # Assert that UNICODE_CHARS is in the dict
            d['test_key2'] = 0
            d['test_key2'] += 1
            
            self.assertEqual(d['test_key2'], 1)

        # The values set inside the "with" are not available "outside"
        # because the format is not compatible (with the dict, the values are stored as a tuple, with the original key stored
        # and with old format, only the value is stored

    def test_old_storage_compat(self) -> None:
        models.Storage.objects.create(
            owner=UNICODE_CHARS,
            key=storage._old_calculate_key(UNICODE_CHARS.encode(), UNICODE_CHARS.encode()),
            data=base64.b64encode((UNICODE_CHARS * 5).encode()).decode(),
        )
        strg = storage.Storage(UNICODE_CHARS)
        # Ensure that key is found
        self.assertEqual(strg.read(UNICODE_CHARS), UNICODE_CHARS * 5)
        # And that now, the key is stored in the new format
        # If not exists, will raise an exception
        models.Storage.objects.get(
            owner=UNICODE_CHARS,
            key=storage._calculate_key(UNICODE_CHARS.encode(), UNICODE_CHARS.encode()),
        )

    def test_storage_as_dict_old(self) -> None:
        models.Storage.objects.create(
            owner=UNICODE_CHARS,
            key=storage._old_calculate_key(UNICODE_CHARS.encode(), UNICODE_CHARS.encode()),
            data=base64.b64encode((UNICODE_CHARS * 5).encode()).decode(),
        )
        strg = storage.Storage(UNICODE_CHARS)

        with strg.as_dict() as d:
            # Assert that UNICODE_CHARS is in the dict (stored with old format)
            self.assertEqual(d[UNICODE_CHARS], UNICODE_CHARS * 5)

        # And that now, the key is stored in the new format
        # If not exists, will raise an exception
        models.Storage.objects.get(
            owner=UNICODE_CHARS,
            key=storage._calculate_key(UNICODE_CHARS.encode(), UNICODE_CHARS.encode()),
        )
