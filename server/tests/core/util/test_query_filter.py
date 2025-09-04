# Copyright (c) 2025 Virtual Cable S.L.U.
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
import copy
import dataclasses
import typing

import unittest

from uds.core.util.query_filter import exec_query  # Ajusta esto al nombre real del archivo si lo separas


class QueryFilterTest(unittest.TestCase):
    data: list[dict[str, typing.Any]]
    objects: list[typing.Any]

    def setUp(self):
        self.data = [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]

        @dataclasses.dataclass
        class TestingObj:
            name: str
            age: int

        self.objects = [
            TestingObj(name="Alice", age=30),
            TestingObj(name="Bob", age=25),
            TestingObj(name="Charlie", age=35),
            TestingObj(name="David", age=30),
        ]

    def test_eq_operator(self):
        result = list(exec_query("name eq 'Alice'", self.data))
        self.assertEqual(result, [{"name": "Alice", "age": 30}])

        # obj
        result = list(exec_query("name eq 'Alice'", self.objects))
        self.assertEqual(result, [self.objects[0]])

    def test_gt_operator(self):
        result = list(exec_query("age gt 30", self.data))
        self.assertEqual(result, [{"name": "Charlie", "age": 35}])

        # obj
        result = list(exec_query("age gt 30", self.objects))
        self.assertEqual(result, [self.objects[2]])

    def test_ge_operator(self):
        result = list(exec_query("age ge 30", self.data))
        self.assertEqual(
            result,
            [
                {"name": "Alice", "age": 30},
                {"name": "Charlie", "age": 35},
                {"name": "David", "age": 30},
            ],
        )

        # obj
        result = list(exec_query("age ge 30", self.objects))
        self.assertEqual(
            result,
            [
                self.objects[0],
                self.objects[2],
                self.objects[3],
            ],
        )

    def test_ne_operator(self):
        result = list(exec_query("name ne 'Bob'", self.data))
        self.assertEqual(
            result,
            [
                {"name": "Alice", "age": 30},
                {"name": "Charlie", "age": 35},
                {"name": "David", "age": 30},
            ],
        )

    def test_and_or_not(self):
        result = list(exec_query("age ge 30 and not name eq 'David'", self.data))
        self.assertEqual(result, [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}])

    def test_startswith_func(self):
        result = list(exec_query("startswith(name,'A')", self.data))
        self.assertEqual(result, [{"name": "Alice", "age": 30}])

    def test_grouped_expression_with_parentheses(self):
        query = "not (age gt 30 or name eq 'Bob')"
        result = list(exec_query(query, self.data))
        # We expect:
        # - Charlie has age > 30 → excluded
        # - Bob has name eq 'Bob' → excluded
        # - Alice and David have age == 30 and name != 'Bob' → included
        expected = [
            {"name": "Alice", "age": 30},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)

    def test_endswith_function(self):
        query = "endswith(name,'e')"
        result = list(exec_query(query, self.data))
        expected = [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_unary_func_length(self):
        result = list(exec_query("length(name) eq 5", self.data))
        expected = [{"name": "Alice", "age": 30}, {"name": "David", "age": 30}]
        self.assertEqual(result, expected)

    def test_toupper_function(self):
        result = list(exec_query("toupper(name) eq 'ALICE'", self.data))
        expected = [{"name": "Alice", "age": 30}]
        self.assertEqual(result, expected)

    def test_tolower_function(self):
        result = list(exec_query("tolower(name) eq 'david'", self.data))
        expected = [{"name": "David", "age": 30}]
        self.assertEqual(result, expected)

    def test_concat_function(self):
        data = [
            {"first": "John", "last": "Doe"},
            {"first": "Jane", "last": "Smith"},
        ]
        result = list(exec_query("concat(first,last) eq 'JohnDoe'", data))
        expected = [{"first": "John", "last": "Doe"}]
        self.assertEqual(result, expected)

        result = list(exec_query("first eq concat('J', 'o', 'h', 'n')", data))
        expected = [{"first": "John", "last": "Doe"}]
        self.assertEqual(result, expected)

    def test_indexof_function_case_sensitive(self):
        result = list(exec_query("indexof(name,'a') ge 0", self.data))
        expected = [
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)

    def test_indexof_function_case_insensitive(self):
        result = list(exec_query("indexof(tolower(name),'a') ge 0", self.data))
        expected = [
            {"name": "Alice", "age": 30},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)

    def test_substringof_function(self):
        result = list(exec_query("substringof('li',name)", self.data))
        expected = [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_contains_function(self):
        result = list(exec_query("contains(name,'li')", self.data))
        expected = [{"name": "Alice", "age": 30}, {"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_substring_function_two_arguments(self):
        result = list(exec_query("substring(name,3) eq 'ce'", self.data))
        expected = [{"name": "Alice", "age": 30}]
        self.assertEqual(result, expected)

    def test_substring_function_three_arguments(self):
        result = list(exec_query("substring(name,1,3) eq 'li'", self.data))
        expected = [{"name": "Alice", "age": 30}]
        self.assertEqual(result, expected)

    def test_year_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_query("year(dob) eq '1990'", data))
        expected = [{"dob": "1990-05-12"}]
        self.assertEqual(result, expected)

    def test_month_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_query("month(dob) eq '11'", data))
        expected = [{"dob": "1985-11-30"}]
        self.assertEqual(result, expected)

    def test_day_function(self):
        data = [
            {"dob": "1990-05-12"},
            {"dob": "1985-11-30"},
        ]
        result = list(exec_query("day(dob) eq '12'", data))
        expected = [{"dob": "1990-05-12"}]
        self.assertEqual(result, expected)

    def test_nested_field_access(self):
        data = [
            {"user": {"name": "Alice"}},
            {"user": {"name": "Bob"}},
        ]
        result = list(exec_query("user.name eq 'Bob'", data))
        expected = [{"user": {"name": "Bob"}}]
        self.assertEqual(result, expected)

    def test_not_with_parentheses(self):
        result = list(exec_query("not (name eq 'Alice')", self.data))
        expected = [
            {"name": "Bob", "age": 25},
            {"name": "Charlie", "age": 35},
            {"name": "David", "age": 30},
        ]
        self.assertEqual(result, expected)

    def test_trim_function(self):
        data_copy = copy.deepcopy(self.data)
        data_copy.append({"name": "  Bella  ", "age": 30})
        result = list(exec_query("trim(name) eq 'Bella'", data_copy))
        expected = [{"name": "  Bella  ", "age": 30}]
        self.assertEqual(result, expected)

    def test_floor_function(self):
        result = list(exec_query("floor(age) eq 25", self.data))
        expected = [{"name": "Bob", "age": 25}]
        self.assertEqual(result, expected)

    def test_ceiling_function(self):
        result = list(exec_query("ceiling(age) eq 35", self.data))
        expected = [{"name": "Charlie", "age": 35}]
        self.assertEqual(result, expected)

    def test_round_function(self):
        result = list(exec_query("round(age) eq 25", self.data))
        expected = [{"name": "Bob", "age": 25}]
        self.assertEqual(result, expected)
