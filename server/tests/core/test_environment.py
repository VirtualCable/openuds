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

from uds.core import environment
from uds.core.util.cache import Cache
from uds.core.util.storage import Storage
from uds.core.util.unique_id_generator import UniqueIDGenerator

from ..utils.test import UDSTestCase


class TestEnvironment(UDSTestCase):
    def test_global_environment(self) -> None:
        env = environment.Environment.get_common_environment()
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self.assertEqual(env.key, environment.GLOBAL_ENV)

    def test_temporary_environment(self) -> None:
        env = environment.Environment.get_temporary_environment()
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self.assertEqual(env.key, environment.TEMP_ENV)

    def test_table_record_environment(self) -> None:
        env = environment.Environment.get_environment_for_table_record('test_table')
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self.assertEqual(env.key, 't-test_table')
        
        env = environment.Environment.get_environment_for_table_record('test_table', 123)
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self.assertEqual(env.key, 't-test_table-123')
        
    def test_environment_for_type(self) -> None:
        env = environment.Environment.get_environment_for_type('test_type')
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self.assertEqual(env.key, 'type-test_type')
        
    def test_unique_environment(self) -> None:
        env = environment.Environment.get_unique_environment()
        self.assertIsInstance(env, environment.Environment)
        self.assertIsInstance(env.cache, Cache)
        self.assertIsInstance(env.storage, Storage)
        self.assertIsInstance(env._id_generators, UniqueIDGenerator)
        self