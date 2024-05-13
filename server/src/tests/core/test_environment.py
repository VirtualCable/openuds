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
import typing

from uds.core import environment
from uds.core.util.cache import Cache
from uds.core.util.storage import Storage

from ..utils.test import UDSTransactionTestCase


class TestEnvironment(UDSTransactionTestCase):
    def _check_environment(
        self,
        env: environment.Environment,
        expected_key: 'str|None',
        is_persistent: bool,
        recreate_fnc: typing.Optional[typing.Callable[[], environment.Environment]] = None,
    ) -> None:
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, dict)
        if expected_key is not None:
            self.assertEqual(env.key, expected_key)

        env.storage.put('test', 'test')
        self.assertEqual(env.storage.read('test'), 'test')

        env.cache.put('test', 'test')
        self.assertEqual(env.cache.get('test'), 'test')

        # Recreate environment
        env = environment.Environment(env.key) if not recreate_fnc else recreate_fnc()

        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, dict)
        if expected_key is not None:
            self.assertEqual(env.key, expected_key)

        if is_persistent:
            self.assertEqual(env.storage.read('test'), 'test')
            self.assertEqual(env.cache.get('test'), 'test')
        else:
            self.assertEqual(env.storage.read('test'), None)
            self.assertEqual(env.cache.get('test'), None)

    def test_global_environment(self) -> None:
        env = environment.Environment.common_environment()
        self._check_environment(env, environment.COMMON_ENV, True)

    def test_temporary_environment(self) -> None:
        env = environment.Environment.testing_environment()
        self._check_environment(env, environment.TEST_ENV, False, recreate_fnc=environment.Environment.testing_environment)

    def test_table_record_environment(self) -> None:
        env = environment.Environment.environment_for_table_record('test_table')
        self._check_environment(env, 't-test_table-', True)

    def test_table_record_environment_with_id(self) -> None:
        env = environment.Environment.environment_for_table_record('test_table', 123)
        self._check_environment(env, 't-test_table-123', True)

    def test_environment_for_type(self) -> None:
        env = environment.Environment.type_environment(TestEnvironment)
        self._check_environment(env, 'type-' + str(TestEnvironment), True)

    def test_exclusive_temporary_environment(self) -> None:
        unique_key: str = ''
        with environment.Environment.temporary_environment() as env:
            self.assertIsInstance(env, environment.Environment)
            self.assertIsInstance(env.cache, Cache)
            self.assertIsInstance(env.storage, Storage)
            self.assertIsInstance(env._id_generators, dict)
            unique_key = env.key  # store for later test

            env.storage.put('test', 'test')
            self.assertEqual(env.storage.read('test'), 'test')

            env.cache.put('test', 'test')
            self.assertEqual(env.cache.get('test'), 'test')

        # Environment is cleared after exit, ensure it
        env = environment.Environment(unique_key)
        with env as env:
            self.assertIsInstance(env, environment.Environment)
            self.assertIsInstance(env.cache, Cache)
            self.assertIsInstance(env.storage, Storage)
            self.assertIsInstance(env._id_generators, dict)
            self.assertEqual(env.key, unique_key)
            self.assertEqual(env.storage.read('test'), None)
            self.assertEqual(env.cache.get('test'), None)
