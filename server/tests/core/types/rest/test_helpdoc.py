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
import dataclasses
import collections.abc
import logging

import typing
from unittest import TestCase

from uds.core.types import rest


logger = logging.getLogger(__name__)


class TestHelpDoc(TestCase):
    def test_helpdoc_basic(self) -> None:
        h = rest.HelpDoc('/path', 'help_text')

        self.assertEqual(h.path, '/path')
        self.assertEqual(h.description, 'help_text')
        self.assertEqual(h.arguments, [])

    def test_helpdoc_with_args(self) -> None:
        arguments = [
            rest.HelpDoc.ArgumentInfo('arg1', 'arg1_type', 'arg1_description'),
            rest.HelpDoc.ArgumentInfo('arg2', 'arg2_type', 'arg2_description'),
        ]
        h = rest.HelpDoc(
            '/path',
            'help_text',
            arguments=arguments,
        )

        self.assertEqual(h.path, '/path')
        self.assertEqual(h.description, 'help_text')
        self.assertEqual(h.arguments, arguments)

    def test_helpdoc_with_args_and_return(self) -> None:
        arguments = [
            rest.HelpDoc.ArgumentInfo('arg1', 'arg1_type', 'arg1_description'),
            rest.HelpDoc.ArgumentInfo('arg2', 'arg2_type', 'arg2_description'),
        ]
        returns = {
            'name': 'return_name',
        }
        h = rest.HelpDoc(
            '/path',
            'help_text',
            arguments=arguments,
            returns=returns,
        )

        self.assertEqual(h.path, '/path')
        self.assertEqual(h.description, 'help_text')
        self.assertEqual(h.arguments, arguments)
        self.assertEqual(h.returns, returns)

    def test_help_doc_from_typed_response(self) -> None:
        @dataclasses.dataclass
        class TestResponse(rest.TypedResponse):
            name: str = 'test_name'
            age: int = 0
            money: float = 0.0

        h = rest.HelpDoc.from_typed_response('path', 'help', TestResponse)

        self.assertEqual(h.path, 'path')
        self.assertEqual(h.description, 'help')
        self.assertEqual(h.arguments, [])
        self.assertEqual(
            h.returns,
            {
                'name': '<string>',
                'age': '<integer>',
                'money': '<float>',
            },
        )

    def test_help_doc_from_typed_response_nested_dataclass(self) -> None:
        @dataclasses.dataclass
        class TestResponse:
            name: str = 'test_name'
            age: int = 0
            money: float = 0.0

        @dataclasses.dataclass
        class TestResponse2(rest.TypedResponse):
            name: str
            age: int
            money: float
            nested: TestResponse

        h = rest.HelpDoc.from_typed_response('path', 'help', TestResponse2)

        self.assertEqual(h.path, 'path')
        self.assertEqual(h.description, 'help')
        self.assertEqual(h.arguments, [])
        self.assertEqual(
            h.returns,
            {
                'name': '<string>',
                'age': '<integer>',
                'money': '<float>',
                'nested': {
                    'name': '<string>',
                    'age': '<integer>',
                    'money': '<float>',
                },
            },
        )

    def test_help_doc_from_fnc(self) -> None:
        @dataclasses.dataclass
        class TestResponse(rest.TypedResponse):
            name: str = 'test_name'
            age: int = 0
            money: float = 0.0

        def testing_fnc() -> TestResponse:
            """
            This is a test function
            """
            return []

        h = rest.HelpDoc.from_fnc('path', 'help', testing_fnc)

        if h is None:
            self.fail('HelpDoc is None')

        self.assertEqual(h.path, 'path')
        self.assertEqual(h.description, 'help')
        self.assertEqual(h.arguments, [])
        self.assertEqual(
            h.returns,
            {
                'name': '<string>',
                'age': '<integer>',
                'money': '<float>',
            },
        )

    def test_help_doc_from_non_typed_response(self) -> None:
        def testing_fnc() -> dict[str, typing.Any]:
            """
            This is a test function
            """
            return {}

        h = rest.HelpDoc.from_fnc('path', 'help', testing_fnc)

        self.assertIsNone(h)
        

    def test_help_doc_from_fnc_list(self) -> None:
        @dataclasses.dataclass
        class TestResponse(rest.TypedResponse):
            name: str = 'test_name'
            age: int = 0
            money: float = 0.0

        def testing_fnc() -> list[TestResponse]:
            """
            This is a test function
            """
            return []

        h = rest.HelpDoc.from_fnc('path', 'help', testing_fnc)

        if h is None:
            self.fail('HelpDoc is None')

        self.assertEqual(h.path, 'path')
        self.assertEqual(h.description, 'help')
        self.assertEqual(h.arguments, [])
        self.assertEqual(
            h.returns,
            [
                {
                    'name': '<string>',
                    'age': '<integer>',
                    'money': '<float>',
                }
            ],
        )
