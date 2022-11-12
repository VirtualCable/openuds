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
import time

from ...utils.test import UDSTestCase
from django.conf import settings
from uds.core.util.unique_id_generator import UniqueIDGenerator
from uds.core.util.unique_gid_generator import UniqueGIDGenerator
from uds.core.util.unique_mac_generator import UniqueMacGenerator
from uds.core.util.unique_name_generator import UniqueNameGenerator
from uds.models import getSqlDatetimeAsUnix


NUM_THREADS = 8
TESTS_PER_TRHEAD = 30

TEST_MAC_RANGE = '00:50:56:10:00:00-00:50:56:3F:FF:FF'  # Testing mac range
TEST_MAC_RANGE_FULL = '00:50:56:10:00:00-00:50:56:10:00:10'  # Testing mac range for NO MORE MACS


def macToInt(mac):
    return int(mac.replace(':', ''), 16)


class UniqueIdTest(UDSTestCase):
    uidGen: UniqueIDGenerator
    ugidGen: UniqueGIDGenerator
    macGen: UniqueMacGenerator
    nameGen: UniqueNameGenerator

    def setUp(self) -> None:
        self.uidGen = UniqueIDGenerator('uidg1', 'test', 'test')
        self.ugidGen = UniqueGIDGenerator('test')
        self.macGen = UniqueMacGenerator('test')
        self.nameGen = UniqueNameGenerator('test')

    def test_seq_uid(self):
        for x in range(100):
            self.assertEqual(self.uidGen.get(), x)

        self.uidGen.free(40)

        self.assertEqual(self.uidGen.get(), 40)

    def test_release_unique_id(self):
        for x in range(100):
            self.uidGen.get()

        self.assertEqual(self.uidGen.get(), 100)

        self.uidGen.release()  # Clear ups

        self.assertEqual(self.uidGen.get(), 0)

    def test_release_older_unique_id(self):
        NUM = 100
        for i in range(NUM):
            self.assertEqual(self.uidGen.get(), i)

        stamp = getSqlDatetimeAsUnix() + 1
        time.sleep(2)

        for i in range(NUM):
            self.assertEqual(self.uidGen.get(), i + NUM)

        self.uidGen.releaseOlderThan(stamp)  # Clear ups older than 0 seconds ago

        for i in range(NUM):
            self.assertEqual(self.uidGen.get(), i)

        # from NUM to NUM*2-1 (both included) are still there, so we should get 200
        self.assertEqual(self.uidGen.get(), NUM*2)
        self.assertEqual(self.uidGen.get(), NUM*2+1)

    def test_gid(self):
        for x in range(100):
            self.assertEqual(self.ugidGen.get(), 'uds{:08d}'.format(x))

    def test_gid_basename(self):
        self.ugidGen.setBaseName('mar')
        for x in range(100):
            self.assertEqual(self.ugidGen.get(), 'mar{:08d}'.format(x))

    def test_mac(self):
        start, end = TEST_MAC_RANGE.split('-')

        self.assertEqual(self.macGen.get(TEST_MAC_RANGE), start)

        starti = macToInt(start) + 1  # We have already got 1 element

        lst = [start]

        for x in range(400):
            mac = self.macGen.get(TEST_MAC_RANGE)
            self.assertEqual(macToInt(mac), starti + x)
            lst.append(mac)

        for x in lst:
            self.macGen.free(x)

        self.assertEqual(self.macGen.get(TEST_MAC_RANGE), start)

    def test_mac_full(self):
        start, end = TEST_MAC_RANGE_FULL.split('-')

        length = macToInt(end) - macToInt(start) + 1

        starti = macToInt(start)

        for x in range(length):
            self.assertEqual(macToInt(self.macGen.get(TEST_MAC_RANGE_FULL)), starti + x)

        for x in range(20):
            self.assertEqual(self.macGen.get(TEST_MAC_RANGE_FULL), '00:00:00:00:00:00')

    def test_name(self):
        lst = []
        num = 0
        for length in range(2, 10):
            for x in range(20):
                name = self.nameGen.get('test', length=length)
                lst.append(name)
                self.assertEqual(name, 'test{:0{width}d}'.format(num, width=length))
                num += 1

        for x in lst:
            self.nameGen.free('test', x)

        self.assertEqual(self.nameGen.get('test', length=1), 'test0')

    def test_name_full(self):
        for x in range(10):
            self.nameGen.get('test', length=1)

        with self.assertRaises(KeyError):
            self.nameGen.get('test', length=1)
