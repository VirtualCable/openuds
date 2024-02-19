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
from functools import cache
from unittest import mock

from ...utils.test import UDSTransactionTestCase
from uds.core.util.decorators import cached
import time


class CacheTest(UDSTransactionTestCase):
    def test_cache_decorator_whole(self) -> None:
        testing_value = 'test'

        @cached(prefix='test', timeout=1)
        def cached_fnc(value: str) -> str:
            return testing_value

        self.assertEqual(cached_fnc('test'), 'test')
        # Now, even changing the value, it will be the same
        testing_value = 'test2'
        self.assertEqual(cached_fnc('test'), 'test')
        # But now, with a different value, it will be different
        self.assertEqual(cached_fnc('test2'), 'test2')

        # Once expired, it will be the new value
        time.sleep(1.1)
        self.assertEqual(cached_fnc('test'), 'test2')

    def test_cache_decorator_args(self) -> None:
        testing_value = 'test'

        @cached(prefix='test', timeout=1, args=[0])
        def cached_fnc(value: str) -> str:
            return testing_value

        self.assertEqual(cached_fnc('test'), 'test')
        # Now, even changing the value, it will be the same
        testing_value = 'test2'
        self.assertEqual(cached_fnc('test'), 'test')
        # But now, with a different value, it will be different
        self.assertEqual(cached_fnc('test2'), 'test2')

    def test_cache_decorator_kwargs(self) -> None:
        testing_value = 'test'

        @cached(prefix='test', timeout=1, kwargs=['value'])
        def cached_fnc(value: str) -> str:
            return testing_value

        self.assertEqual(cached_fnc('test'), 'test')
        # Now, even changing the value, it will be the same
        testing_value = 'test2'
        self.assertEqual(cached_fnc('test'), 'test')
        # With a different value, it will be the same (because we cached only keyword args)
        self.assertEqual(cached_fnc('test2'), 'test')
        # But now, with a different value, it will be different using keyword args
        self.assertEqual(cached_fnc(value='test2'), 'test2')

    def test_cache_decorator_key_fnc(self) -> None:
        cache_key = mock.MagicMock(return_value='test')

        class Test:
            value: list[str]
            call_count = 0

            def __init__(self, value: str):
                self.value = [value] * 8

            @cached(prefix='test', timeout=1, key_helper=cache_key)
            def cached_test(self, **kwargs) -> list[str]:
                self.call_count += 1
                return self.value

        test = Test('test')
        orig_value = test.value
        self.assertEqual(test.cached_test(), orig_value)
        self.assertEqual(cache_key.call_count, 1)
        self.assertEqual(test.call_count, 1)

        test.value = ['test2'] * 8
        TESTS_COUNT = 32
        for i in range(TESTS_COUNT):
            self.assertEqual(test.cached_test(), orig_value)
            self.assertEqual(cache_key.call_count, i+2)
            self.assertEqual(cache_key.call_args[0][0], test)
            self.assertEqual(test.call_count, 1)

        # Wait for cache to expire
        time.sleep(1.1)
        self.assertEqual(test.cached_test(), test.value)
        self.assertEqual(cache_key.call_count, TESTS_COUNT+2)
        self.assertEqual(cache_key.call_args[0][0], test)
        self.assertEqual(test.call_count, 2)

        # Now lets tests with force, no matter timeout
        test.value = ['test3'] * 8
        self.assertEqual(test.cached_test(force=True), test.value)
        self.assertEqual(cache_key.call_count, TESTS_COUNT+3)
        self.assertEqual(cache_key.call_args[0][0], test)
        self.assertEqual(test.call_count, 3)
        
        test.value = ['test4'] * 8
        self.assertEqual(test.cached_test(force=True), test.value)
        self.assertEqual(cache_key.call_count, TESTS_COUNT+4)
        self.assertEqual(cache_key.call_args[0][0], test)
        self.assertEqual(test.call_count, 4)
        