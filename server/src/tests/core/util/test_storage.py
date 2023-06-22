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

from ...utils.test import UDSTestCase
from uds.core.util.storage import Storage

UNICODE_CHARS = 'ñöçóá^(pípè)'
UNICODE_CHARS_2 = 'ñöçóá^(€íöè)'
VALUE_1 = ['unicode', b'string', {'a': 1, 'b': 2.0}]


class StorageTest(UDSTestCase):
    def test_storage(self):
        storage = Storage(UNICODE_CHARS)

        storage.put(UNICODE_CHARS, b'chars')
        storage.saveData('saveData', UNICODE_CHARS, UNICODE_CHARS)
        storage.saveData('saveData2', UNICODE_CHARS_2, UNICODE_CHARS)
        storage.saveData('saveData3', UNICODE_CHARS, 'attribute')
        storage.saveData('saveData4', UNICODE_CHARS_2, 'attribute')
        storage.put(b'key', UNICODE_CHARS)
        storage.put(UNICODE_CHARS_2, UNICODE_CHARS)

        storage.putPickle('pickle', VALUE_1)

        self.assertEqual(storage.get(UNICODE_CHARS), u'chars')  # Always returns unicod
        self.assertEqual(storage.readData('saveData'), UNICODE_CHARS)
        self.assertEqual(storage.readData('saveData2'), UNICODE_CHARS_2)
        self.assertEqual(storage.get(b'key'), UNICODE_CHARS)
        self.assertEqual(storage.get(UNICODE_CHARS_2), UNICODE_CHARS)
        self.assertEqual(storage.getPickle('pickle'), VALUE_1)

        self.assertEqual(len(list(storage.locateByAttr1(UNICODE_CHARS))), 2)
        self.assertEqual(len(list(storage.locateByAttr1('attribute'))), 2)

        storage.remove(UNICODE_CHARS)
        storage.remove(b'key')
        storage.remove('pickle')

        self.assertIsNone(storage.get(UNICODE_CHARS))
        self.assertIsNone(storage.get(b'key'))
        self.assertIsNone(storage.getPickle('pickle'))
