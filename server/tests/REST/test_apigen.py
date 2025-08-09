# -*- coding: utf-8 -*-
#
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
import dataclasses
import typing
import logging
import enum

from tests.utils.test import UDSTestCase

from uds.REST import dispatcher, model
from uds.core import types


logger = logging.getLogger(__name__)


class TestApiGenBasic(UDSTestCase):
    def test_model_enum_schemas_for_api(self):
        root_node = dispatcher.Dispatcher.root_node

        # Node is a tree, recursively check all children
        def check_node(node: types.rest.HandlerNode):
            logger.info("Checking child node: %s", node.name)
            if node.handler and issubclass(node.handler, model.ModelHandler):
                handler = typing.cast(model.ModelHandler[typing.Any], typing.cast(typing.Any, node).handler)
                logger.info("Checking handler: %s", handler)
                schema = handler.api_component()
                logger.info("Found enum schema for API: %s=%s", schema.as_dict())
                self.assertIsInstance(schema, types.rest.api.Components)
            for child in node.children.values():
                check_node(child)

        check_node(root_node)

    def test_python_type_to_openapi(self):
        # Test basic types
        self.assertEqual(
            types.rest.api.python_type_to_openapi(int), types.rest.api.SchemaProperty(type='integer')
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(str), types.rest.api.SchemaProperty(type='string')
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(float), types.rest.api.SchemaProperty(type='number')
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(bool), types.rest.api.SchemaProperty(type='boolean')
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(type(None)), types.rest.api.SchemaProperty(type='"null"')
        )

        # Test list, dict, union and enums (Enum, IntEnum, StrEnum)
        self.assertEqual(
            types.rest.api.python_type_to_openapi(list[str]),
            types.rest.api.SchemaProperty(type='array', items=types.rest.api.SchemaProperty(type='string')),
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(dict[str, str]),
            types.rest.api.SchemaProperty(
                type='object', additionalProperties=types.rest.api.SchemaProperty(type='string')
            ),
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(typing.Union[int, str]),
            types.rest.api.SchemaProperty(type=['integer', 'string']),
        )
        self.assertEqual(
            types.rest.api.python_type_to_openapi(enum.Enum),
            types.rest.api.SchemaProperty(type='string'),
        )

        class MyEnum(enum.Enum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        self.assertEqual(
            types.rest.api.python_type_to_openapi(MyEnum),
            types.rest.api.SchemaProperty(type='string', enum=[e.value for e in MyEnum]),
        )

    def test_base_rest_item_api_components(self):

        class MyEnum(enum.Enum):
            VALUE1 = "value1"
            VALUE2 = "value2"

        @dataclasses.dataclass
        class TestItem(types.rest.BaseRestItem):
            field_str: str
            field_int: int
            field_float: float
            field_list: typing.List[str] = dataclasses.field(default_factory=list[str])
            field_list_2: list[str] = dataclasses.field(default_factory=list[str])
            field_dict: typing.Dict[str, str] = dataclasses.field(default_factory=dict[str, str])
            field_dict_2: dict[str, str] = dataclasses.field(default_factory=dict[str, str])
            field_enum: MyEnum = MyEnum.VALUE1
            field_optional: typing.Optional[str] = None
            field_union: typing.Union[str, int] = "value"
            field_union_2: str | int = 1

        components = TestItem.api_components()

        self.assertIsInstance(components, types.rest.api.Components)