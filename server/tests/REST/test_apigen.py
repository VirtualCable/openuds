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

from uds.REST import dispatcher
from uds.REST.model import base
from uds.REST.model.master import ModelHandler
from uds.core import types, transports, consts, ui
from uds.core.util import api as util_api
from uds.models import Transport

logger = logging.getLogger(__name__)


class MyEnum(enum.Enum):
    VALUE1 = "value1"
    VALUE2 = "value2"


@dataclasses.dataclass
class BaseRestItem(types.rest.BaseRestItem):
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


class TestTransport(transports.Transport):
    """
    Simpe testing transport. Currently a copy of URLCustomTransport
    """

    type_name = 'Test Transport'
    type_type = 'TestTransport'
    type_description = 'Test Transport'
    icon_file = 'transport.png'

    own_link = True
    supported_oss = consts.os.ALL_OS_LIST
    PROTOCOL = types.transports.Protocol.OTHER
    group = types.transports.Grouping.DIRECT

    text_fld = ui.gui.TextField(label='text_fld', tooltip='text_fld tooltip', required=True)
    text_auto_fld = ui.gui.TextAutocompleteField(
        label='text_auto_fld', tooltip='text_auto_fld tooltip', required=True
    )
    num_fld = ui.gui.NumericField(label='num_fld', tooltip='num_fld tooltip', required=True)
    pass_fld = ui.gui.PasswordField(label='pass_fld', tooltip='pass_fld tooltip', required=True)
    hidden_fld = ui.gui.HiddenField(label='hidden_fld')
    choice_fld = ui.gui.ChoiceField(label='choice_fld', tooltip='choice_fld tooltip', required=True)
    multi_choice_fld = ui.gui.MultiChoiceField(
        label='multi_choice_fld', tooltip='multi_choice_fld tooltip', required=True
    )
    editable_list_fld = ui.gui.EditableListField(
        label='editable_list_fld', tooltip='editable_list_fld tooltip', required=True
    )
    checkbox_fld = ui.gui.CheckBoxField(label='checkbox_fld', tooltip='checkbox_fld tooltip', required=True)
    image_choice_fld = ui.gui.ImageChoiceField(
        label='image_choice_fld', tooltip='image_choice_fld tooltip', required=True
    )
    date_fld = ui.gui.DateField(label='date_fld', tooltip='date_fld tooltip', required=True)
    info_fld = ui.gui.HelpField(label='info_fld', title='help', help='help text')


@dataclasses.dataclass
class ManagedObjectRestItem(types.rest.ManagedObjectItem[Transport]):
    field_str: str
    field_union: str | int | None = None


class TestApiGenBasic(UDSTestCase):
    def test_model_handler_componments(self) -> None:
        root_node = dispatcher.Dispatcher.root_node

        comps = base.BaseModelHandler.common_components()
        paths = base.BaseModelHandler.common_paths()

        # Node is a tree, recursively check all children
        def check_node(node: types.rest.HandlerNode):
            nonlocal comps
            if handler := node.handler:
                path = node.full_path()
                logger.info("Checking child node: %s, %s", node.name, handler.__module__)
                components = handler.api_components()
                # Component should not be empty
                self.assertIsInstance(
                    components,
                    types.rest.api.Components,
                    f'Component for {node.name} should be of type Components',
                )

                handler_paths = handler.api_paths(path, [path.split('/')[0].capitalize()])
                self.assertIsInstance(
                    handler_paths,
                    dict,
                    f'Paths for {node.name} should be of type Paths',
                )
                for path, item in handler_paths.items():
                    self.assertIsInstance(
                        path,
                        str,
                        f'Path for {node.name} should be of type str',
                    )
                    self.assertIsInstance(
                        item,
                        types.rest.api.PathItem,
                        f'Path item for {node.name} path {path} should be of type PathItem',
                    )
                # self.assertFalse(components.is_empty(), f'Component for model {node.name} ({node.handler.__module__}) should not be empty')
                comps = comps.union(components)
                paths.update(handler_paths)
                
                # If is a ModelHandler, look for DETAIL
                if issubclass(handler, ModelHandler) and handler.DETAIL:
                    for name, cls in handler.DETAIL.items():
                        logger.info("Found detail for %s: %s", node.name, name)
                        
                        comps = comps.union(cls.api_components())
                        paths.update(cls.api_paths(f'{path}/{name}', []))

            for child in node.children.values():
                check_node(child)

        check_node(root_node)
        logger.info("Components found: %s", ', '.join(comps.schemas.keys()))
        logger.info("Paths found: %s", ', '.join(paths.keys()))

        import json
        import yaml

        api = types.rest.api.OpenAPI(paths=paths, components=comps)

        with open('/tmp/uds_api.json', 'w') as f:
            f.write(json.dumps(api.as_dict(), indent=4))

        with open('/tmp/uds_api.yaml', 'w') as f:
            f.write(yaml.dump(api.as_dict()))

    def test_handler_urls(self) -> None:
        root_node = dispatcher.Dispatcher.root_node
        for line in root_node.tree().splitlines():
            logger.info('*> %s', line)

        def process_node(
            node: 'types.rest.HandlerNode',
            path: str,
            type_: str,
            level: int,
        ) -> None:
            if node.handler is None:
                raise ValueError(f'Node {node.name} has no handler, cannot process')
            logger.info("Processing node: %s, %s", node.name, type_)
            # 'handler', 'custom_method', 'detail_method'
            match type_:
                case 'custom_method':
                    pass
                case 'detail_method':
                    pass
                case 'handler':
                    pass
                case _:
                    raise ValueError(f'Unknown type {type_} for node {node.name}')

        root_node.visit(process_node)

    def test_python_type_to_openapi(self) -> None:
        # Test basic types
        self.assertEqual(util_api.python_type_to_openapi(int), types.rest.api.SchemaProperty(type='integer'))
        self.assertEqual(util_api.python_type_to_openapi(str), types.rest.api.SchemaProperty(type='string'))
        self.assertEqual(util_api.python_type_to_openapi(float), types.rest.api.SchemaProperty(type='number'))
        self.assertEqual(util_api.python_type_to_openapi(bool), types.rest.api.SchemaProperty(type='boolean'))
        self.assertEqual(
            util_api.python_type_to_openapi(type(None)), types.rest.api.SchemaProperty(type='"null"')
        )

        # Test list, dict, union and enums (Enum, IntEnum, StrEnum)
        self.assertEqual(
            util_api.python_type_to_openapi(list[str]),
            types.rest.api.SchemaProperty(type='array', items=types.rest.api.SchemaProperty(type='string')),
        )
        self.assertEqual(
            util_api.python_type_to_openapi(dict[str, str]),
            types.rest.api.SchemaProperty(
                type='object', additionalProperties=types.rest.api.SchemaProperty(type='string')
            ),
        )
        self.assertEqual(
            util_api.python_type_to_openapi(typing.Union[int, str]),
            types.rest.api.SchemaProperty(type=['integer', 'string']),
        )
        self.assertEqual(
            util_api.python_type_to_openapi(enum.Enum),
            types.rest.api.SchemaProperty(type='string'),
        )

        self.assertEqual(
            util_api.python_type_to_openapi(MyEnum),
            types.rest.api.SchemaProperty(type='string', enum=[e.value for e in MyEnum]),
        )

    def test_base_rest_item_api_componentss(self) -> None:

        components = BaseRestItem.api_components()

        self.assertIsInstance(components, types.rest.api.Components)
        self.assertIn('BaseRestItem', components.schemas)
        schema = components.schemas['BaseRestItem']
        self.assertIsInstance(schema, types.rest.api.Schema)
        self.assertEqual(schema.type, 'object')
        self.assertEqual(schema.required, ['field_str', 'field_int', 'field_float'])
        properties = schema.properties
        self.assertIn('field_str', properties)
        self.assertEqual(properties['field_str'], types.rest.api.SchemaProperty(type='string'))
        self.assertIn('field_int', properties)
        self.assertEqual(properties['field_int'], types.rest.api.SchemaProperty(type='integer'))
        self.assertIn('field_float', properties)
        self.assertEqual(properties['field_float'], types.rest.api.SchemaProperty(type='number'))
        self.assertIn('field_list', properties)
        self.assertEqual(
            properties['field_list'],
            types.rest.api.SchemaProperty(type='array', items=types.rest.api.SchemaProperty(type='string')),
        )
        self.assertIn('field_dict', properties)
        self.assertEqual(
            properties['field_dict'],
            types.rest.api.SchemaProperty(
                type='object', additionalProperties=types.rest.api.SchemaProperty(type='string')
            ),
        )
        self.assertIn('field_enum', properties)
        self.assertEqual(
            properties['field_enum'],
            types.rest.api.SchemaProperty(type='string', enum=[e.value for e in MyEnum]),
        )
        self.assertIn('field_optional', properties)
        self.assertEqual(properties['field_optional'], types.rest.api.SchemaProperty(type=['string', 'null']))
        self.assertIn('field_union', properties)
        self.assertEqual(properties['field_union'], types.rest.api.SchemaProperty(type=['string', 'integer']))
        self.assertIn('field_union_2', properties)
        self.assertEqual(properties['field_union_2'], types.rest.api.SchemaProperty(type=['string', 'integer']))

    def test_base_rest_item_as_dict(self) -> None:
        components = BaseRestItem.api_components()

        dct = components.as_dict()

        self.assertEqual(
            dct,
            {
                'schemas': {
                    'BaseRestItem': {
                        'type': 'object',
                        'properties': {
                            'field_str': {'type': 'string'},
                            'field_int': {'type': 'integer'},
                            'field_float': {'type': 'number'},
                            'field_list': {'type': 'array', 'items': {'type': 'string'}},
                            'field_list_2': {'type': 'array', 'items': {'type': 'string'}},
                            'field_dict': {'type': 'object', 'additionalProperties': {'type': 'string'}},
                            'field_dict_2': {'type': 'object', 'additionalProperties': {'type': 'string'}},
                            'field_enum': {'type': 'string', 'enum': ['value1', 'value2']},
                            'field_optional': {'oneOf': [{'type': 'string'}, {'type': 'null'}]},
                            'field_union': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]},
                            'field_union_2': {'oneOf': [{'type': 'string'}, {'type': 'integer'}]},
                        },
                        'required': ['field_str', 'field_int', 'field_float'],
                    }
                }
            },
        )

    def test_managed_object_schema(self) -> None:
        components = ManagedObjectRestItem.api_components()

        self.assertIsInstance(components, types.rest.api.Components)
        self.assertIn('ManagedObjectRestItem', components.schemas)
        schema = components.schemas['ManagedObjectRestItem']
        self.assertIsInstance(schema, types.rest.api.Schema)
        self.assertEqual(schema.type, 'object')
        self.assertEqual(schema.required, ['field_str', 'type', 'instance'])
        properties = schema.properties
        self.assertIn('field_str', properties)
        self.assertEqual(properties['field_str'], types.rest.api.SchemaProperty(type='string'))
        self.assertIn('field_union', properties)
        self.assertEqual(
            properties['field_union'], types.rest.api.SchemaProperty(type=['string', 'integer', 'null'])
        )
        self.assertIn('type', properties)
        self.assertEqual(properties['type'], types.rest.api.SchemaProperty(type='string'))
        self.assertIn('type_name', properties)
        self.assertEqual(properties['type_name'], types.rest.api.SchemaProperty(type='string'))
        self.assertIn('instance', properties)
        self.assertEqual(properties['instance'], types.rest.api.SchemaProperty(type='object'))
