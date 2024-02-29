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

from uds.core.util.unique_id_generator import UniqueIDGenerator
from uds.core.util.unique_gid_generator import UniqueGIDGenerator
from uds.core.util.unique_mac_generator import UniqueMacGenerator
from uds.core.util.unique_name_generator import UniqueNameGenerator

from uds.core.util.model import sql_stamp_seconds

from ...utils.test import UDSTestCase


NUM_THREADS = 8
TESTS_PER_TRHEAD = 30

TEST_MAC_RANGE = '00:50:56:10:00:00-00:50:56:3F:FF:FF'  # Testing mac range
TEST_MAC_RANGE_FULL = '00:50:56:10:00:00-00:50:56:10:00:10'  # Testing mac range for NO MORE MACS


def mac_to_integer(mac: str) -> int:
    return int(mac.replace(':', ''), 16)


class UniqueIdTest(UDSTestCase):
    uniqueid_generator: UniqueIDGenerator
    ugidGen: UniqueGIDGenerator
    macs_generator: UniqueMacGenerator
    name_generator: UniqueNameGenerator

    def setUp(self) -> None:
        self.uniqueid_generator = UniqueIDGenerator('test', 'test')
        self.ugidGen = UniqueGIDGenerator('test')
        self.macs_generator = UniqueMacGenerator('test')
        self.name_generator = UniqueNameGenerator('test')

    def test_seq_uid(self) -> None:
        for x in range(100):
            self.assertEqual(self.uniqueid_generator.get(), x)

        self.uniqueid_generator.free(40)

        self.assertEqual(self.uniqueid_generator.get(), 40)

    def test_release_unique_id(self) -> None:
        for _ in range(100):
            self.uniqueid_generator.get()

        self.assertEqual(self.uniqueid_generator.get(), 100)

        self.uniqueid_generator.release()  # Clear ups

        self.assertEqual(self.uniqueid_generator.get(), 0)

    def test_release_older_unique_id(self) -> None:
        NUM = 100
        for i in range(NUM):
            self.assertEqual(self.uniqueid_generator.get(), i)

        stamp = sql_stamp_seconds() + 1
        time.sleep(2)

        for i in range(NUM):
            self.assertEqual(self.uniqueid_generator.get(), i + NUM)

        self.uniqueid_generator.release_older_than(stamp)  # Clear ups older than 0 seconds ago

        for i in range(NUM):
            self.assertEqual(self.uniqueid_generator.get(), i)

        # from NUM to NUM*2-1 (both included) are still there, so we should get 200
        self.assertEqual(self.uniqueid_generator.get(), NUM * 2)
        self.assertEqual(self.uniqueid_generator.get(), NUM * 2 + 1)

    def test_gid(self) -> None:
        for x in range(100):
            self.assertEqual(self.ugidGen.get(), f'uds{x:08d}')

    def test_gid_basename(self) -> None:
        self.ugidGen.set_basename('mar')
        for x in range(100):
            self.assertEqual(self.ugidGen.get(), f'mar{x:08d}')

    def test_mac(self) -> None:
        start, _end = TEST_MAC_RANGE.split('-')  # pylint: disable=unused-variable

        self.assertEqual(self.macs_generator.get(TEST_MAC_RANGE), start)

        starti = mac_to_integer(start) + 1  # We have already got 1 element

        lst = [start]

        for x in range(400):
            mac = self.macs_generator.get(TEST_MAC_RANGE)
            self.assertEqual(mac_to_integer(mac), starti + x)
            lst.append(mac)

        for x in lst:
            self.macs_generator.free(x)

        self.assertEqual(self.macs_generator.get(TEST_MAC_RANGE), start)

    def test_mac_full(self) -> None:
        start, end = TEST_MAC_RANGE_FULL.split('-')

        length = mac_to_integer(end) - mac_to_integer(start) + 1

        starti = mac_to_integer(start)

        for x in range(length):
            self.assertEqual(mac_to_integer(self.macs_generator.get(TEST_MAC_RANGE_FULL)), starti + x)

        for x in range(20):
            self.assertEqual(self.macs_generator.get(TEST_MAC_RANGE_FULL), '00:00:00:00:00:00')

    def test_name(self) -> None:
        lst: list[str] = []
        num = 0
        for length in range(2, 10):
            for x in range(20):
                name = self.name_generator.get('test', length=length)
                lst.append(name)
                self.assertEqual(name, f'test{num:0{length}d}'.format(num, width=length))
                num += 1

        for x in lst:
            self.name_generator.free('test', x)

        self.assertEqual(self.name_generator.get('test', length=1), 'test0')

    def test_name_full(self) -> None:
        for _ in range(10):
            self.name_generator.get('test', length=1)

        with self.assertRaises(KeyError):
            self.name_generator.get('test', length=1)
