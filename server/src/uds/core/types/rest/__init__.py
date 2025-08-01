# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
# pyright: reportUnusedImport=false

import abc
import enum
import collections.abc
import typing
import dataclasses

from uds.core import types

from . import doc
from . import stock
from . import actor

if typing.TYPE_CHECKING:
    from uds.REST.handlers import Handler
    from uds.models.managed_object_model import ManagedObjectModel


@dataclasses.dataclass
class TypeInfo:
    name: str
    type: str
    description: str
    icon: str

    group: typing.Optional[str] = None

    extra: 'ExtraTypeInfo|None' = None

    def as_dict(self) -> dict[str, typing.Any]:
        res: dict[str, typing.Any] = {
            'name': self.name,
            'type': self.type,
            'description': self.description,
            'icon': self.icon,
        }
        # Add optional fields
        if self.group:
            res['group'] = self.group

        if self.extra:
            res.update(self.extra.as_dict())

        return res

    @staticmethod
    def null() -> 'TypeInfo':
        return TypeInfo(name='', type='', description='', icon='', extra=None)


class ExtraTypeInfo(abc.ABC):
    def as_dict(self) -> dict[str, typing.Any]:
        return {}


@dataclasses.dataclass
class AuthenticatorTypeInfo(ExtraTypeInfo):
    search_users_supported: bool
    search_groups_supported: bool
    needs_password: bool
    label_username: str
    label_groupname: str
    label_password: str
    create_users_supported: bool
    is_external: bool
    mfa_data_enabled: bool
    mfa_supported: bool

    def as_dict(self) -> dict[str, typing.Any]:
        return dataclasses.asdict(self)


class NotRequired:
    """
    This is a marker class to indicate that a field is not required.
    It is used to indicate that a field is optional in the REST API.
    """

    def __bool__(self) -> bool:
        return False

    def __str__(self) -> str:
        return 'NotRequired'
    
    # Field generator for dataclasses
    @staticmethod
    def field() -> typing.Any:
        """
        Returns a field that is not required.
        This is used to indicate that a field is optional in the REST API.
        """
        return dataclasses.field(default_factory=lambda: NotRequired(), repr=False, compare=False)


# This is a named tuple for convenience, and must be
# compatible with tuple[str, bool] (name, needs_parent)
@dataclasses.dataclass
class ModelCustomMethod:
    name: str
    needs_parent: bool = True


# Note that for this item to work with documentation
# no forward references can be used (that is, do not use quotes around the inner field types)
@dataclasses.dataclass
class BaseRestItem:

    def as_dict(self) -> dict[str, typing.Any]:
        """
        Returns a dictionary representation of the item.
        By default, it returns the dataclass fields as a dictionary.
        """
        return dataclasses.asdict(self)

        # NOTE: the json processor should take care of converting "sub-items" to valid dictionaries
        #
        # This code is keept here for future reference, but not used right now
        # def _process_item(key: str, value: typing.Any) -> typing.Any:
        #     """
        #     Process each item in the dictionary.
        #     If the item is a BaseRestItem, call its as_dict method.
        #     If the item is an iterable, iterate over it and call as_dict on each item.
        #     If the item is a mapping, iterate over it and call as_dict on each value.
        #     """
        #     # if it's a basic type, we just return it
        #     # Avoid this traetment for strings for example, as they are also collections.abc.Iterable
        #     if isinstance(value, (str, int, float, bool, type(None))):
        #         return value
        #     if isinstance(value, BaseRestItem):
        #         value = value.as_dict()
        #     # It its an iterable, we iterate over it and call as_dict on each item
        #     elif isinstance(value, collections.abc.Iterable):
        #         value = [
        #             item.as_dict() if isinstance(item, BaseRestItem) else item
        #             for item in typing.cast(collections.abc.Iterable[typing.Any], value)
        #         ]
        #     elif isinstance(value, collections.abc.Mapping):
        #         value = {
        #             k: v.as_dict() if isinstance(v, BaseRestItem) else v
        #             for k, v in typing.cast(collections.abc.Mapping[typing.Any, typing.Any], value).items()
        #         }

        #     return value

        # return {k: _process_item(k, v) for k, v in dct.items() if not isinstance(v, NotRequired)}


T_Model = typing.TypeVar('T_Model', bound='ManagedObjectModel')


@dataclasses.dataclass
class ManagedObjectItem(BaseRestItem, typing.Generic[T_Model]):
    """
    Represents a managed object type, with its name and type.
    This is used to represent the type of a managed object in the REST API.
    """

    item: T_Model

    def as_dict(self) -> dict[str, typing.Any]:
        """
        Returns a dictionary representation of the managed object item.
        """
        base = super().as_dict()
        # Remove the fields that are not needed in the dictionary
        base.pop('item')
        item = self.item.get_instance()
        item.init_gui()  # Defaults & stuff
        fields = item.get_fields_as_dict()

        # TODO: This will be removed in future versions, as it will be overseed by "instance" key
        base.update(fields)  # Add fields to dict
        base.update(
            {
                'type': item.mod_type(),  # Add type
                'type_name': item.mod_name(),  # Add type name
                'instance': fields,  # Future implementation will insert instance fields into "instance" key
            }
        )

        return base


# Alias for item type
T_Item = typing.TypeVar("T_Item", bound=BaseRestItem)

# Alias for get_items return type
ItemsResult: typing.TypeAlias = list[T_Item] | BaseRestItem | typing.Iterator[T_Item]


class TableFieldType(enum.StrEnum):
    """
    Enum for table field types.
    This is used to define the type of a field in a table.
    """

    NUMERIC = 'numeric'
    ALPHANUMERIC = 'alphanumeric'
    BOOLEAN = 'boolean'
    DATETIME = 'datetime'
    DATETIMESEC = 'datetimesec'
    DATE = 'date'
    TIME = 'time'
    ICON = 'icon'
    DICTIONARY = 'dictionary'
    IMAGE = 'image'


@dataclasses.dataclass
class TableField:
    """
    Represents a field in a table, with its title and type.
    This is used to describe the fields of a table in the REST API.
    """

    name: str  # Name of the field, used as key in the table

    title: str  # Title of the field
    type: TableFieldType = TableFieldType.ALPHANUMERIC  # Type of the field, defaults to alphanumeric
    visible: bool = True
    width: str | None = None  # Width of the field, if applicable
    dct: dict[typing.Any, typing.Any] | None = None  # Dictionary for dictionary fields, if applicable

    def as_dict(self) -> dict[str, typing.Any]:
        # Only return the fields that are set

        res: dict[str | int, typing.Any] = {
            'title': self.title,
            'type': self.type.value,
            'visible': self.visible,
        }
        if self.dct:
            res['dict'] = self.dct
        if self.width:
            res['width'] = self.width
        return {self.name: res}  # Return as a dictionary with the field name as key


@dataclasses.dataclass
class RowStyleInfo:
    prefix: str
    field: str

    def as_dict(self) -> dict[str, typing.Any]:
        """Returns a dict with all fields that are not None"""
        return dataclasses.asdict(self)

    @staticmethod
    def null() -> 'RowStyleInfo':
        return RowStyleInfo('', '')


@dataclasses.dataclass
class Table:
    """
    Represents the table info for a REST API endpoint.
    This is used to describe the table fields and row style.
    """

    title: str
    fields: list[TableField]  # List of fields in the table
    row_style: 'RowStyleInfo'
    subtitle: typing.Optional[str] = None

    def as_dict(self) -> dict[str, typing.Any]:
        return {
            'title': self.title,
            'fields': [field.as_dict() for field in self.fields],
            'row_style': self.row_style.as_dict(),
            'subtitle': self.subtitle or '',
        }

    @staticmethod
    def null() -> 'Table':
        """
        Returns a null TableInfo instance, with no fields and an empty title.
        """
        return Table(title='', fields=[], row_style=RowStyleInfo.null(), subtitle=None)


@dataclasses.dataclass(frozen=True)
class HandlerNode:
    """
    Represents a node on the handler tree for rest services
    """

    name: str
    handler: typing.Optional[type['Handler']]
    parent: typing.Optional['HandlerNode']
    children: dict[str, 'HandlerNode']

    def __str__(self) -> str:
        return f'HandlerNode({self.name}, {self.handler}, {self.children})'

    def __repr__(self) -> str:
        return str(self)

    def tree(self, level: int = 0) -> str:
        """
        Returns a string representation of the tree
        """
        from uds.REST.model import ModelHandler

        if self.handler is None:
            return f'{"  " * level}|- {self.name}\n' + ''.join(
                child.tree(level + 1) for child in self.children.values()
            )

        ret = f'{"  " * level}{self.name} ({self.handler.__name__}  {self.full_path()})\n'

        if issubclass(self.handler, ModelHandler):
            # We don't mind the type of handler here, as we are just using it for introspection
            handler = typing.cast(
                ModelHandler[typing.Any], self.handler  # pyright: ignore[reportUnknownMemberType]
            )

            # Add custom_methods
            for method in handler.CUSTOM_METHODS:
                ret += f'{"  " * level}  |- {method}\n'
            # Add detail methods
            if handler.DETAIL:
                for method_name in handler.DETAIL.keys():
                    ret += f'{"  " * level}  |- {method_name}\n'

        return ret + ''.join(child.tree(level + 1) for child in self.children.values())

    def help_node(self) -> doc.HelpNode:
        """
        Returns a HelpNode for this node (and children recursively)
        """
        from uds.REST.model import ModelHandler

        custom_help: set[doc.HelpNode] = set()

        help_node_type = doc.HelpNode.Type.PATH

        if not self.handler:
            # If no handler, this is a path node, so we return a path node
            return doc.HelpNode(
                doc.HelpDoc(path=self.full_path(), help=self.name),
                [child.help_node() for child in self.children.values()],
                help_node_type,
            )

        # Cast here, but may be not a ModelHandler, so we need to check later
        handler = typing.cast(
            ModelHandler[typing.Any], self.handler
        )  # pyright: ignore[reportUnknownMemberType]
        help_node_type = doc.HelpNode.Type.CUSTOM

        if issubclass(self.handler, ModelHandler):
            help_node_type = doc.HelpNode.Type.MODEL
            # Add custom_methods
            for method in handler.CUSTOM_METHODS:
                # Method is a Me CustomModelMethod,
                # We access the __doc__ of the function inside the handler with method.name
                doc_attr = getattr(handler, method.name).__doc__ or ''
                path = (
                    f'{self.full_path()}/{method.name}'
                    if not method.needs_parent
                    else f'{self.full_path()}/<uuid>/{method.name}'
                )
                custom_help.add(
                    doc.HelpNode(
                        doc.HelpDoc(path=path, help=doc_attr),
                        [],
                        doc.HelpNode.Type.CUSTOM,
                    )
                )

            # Add detail methods
            if handler.DETAIL:
                for method_name, method_class in handler.DETAIL.items():
                    custom_help.add(
                        doc.HelpNode(
                            doc.HelpDoc(path=self.full_path() + '/' + method_name, help=''),
                            [],
                            doc.HelpNode.Type.DETAIL,
                        )
                    )
                    # Add custom_methods
                    for detail_method in method_class.CUSTOM_METHODS:
                        # Method is a Me CustomModelMethod,
                        # We access the __doc__ of the function inside the handler with method.name
                        doc_attr = getattr(method_class, detail_method).__doc__ or ''
                        custom_help.add(
                            doc.HelpNode(
                                doc.HelpDoc(
                                    path=self.full_path()
                                    + '/<uuid>/'
                                    + method_name
                                    + '/<uuid>/'
                                    + detail_method,
                                    help=doc_attr,
                                ),
                                [],
                                doc.HelpNode.Type.CUSTOM,
                            )
                        )

            custom_help |= {
                doc.HelpNode(
                    doc.HelpDoc(
                        path=self.full_path() + '/' + help_info.path,
                        help=help_info.description,
                    ),
                    [],
                    help_node_type,
                )
                for help_info in handler.HELP_PATHS
            }

        custom_help |= {child.help_node() for child in self.children.values()}

        return doc.HelpNode(
            help=doc.HelpDoc(path=self.full_path(), help=handler.__doc__ or ''),
            children=list(custom_help),
            kind=help_node_type,
        )

    def find_path(self, path: str | list[str]) -> typing.Optional['HandlerNode']:
        """
        Returns the node for a given path, or None if not found
        """
        if not path or not self.children:
            return self

        # Remove any trailing '/' to allow some "bogus" paths with trailing slashes
        path = path.lstrip('/').split('/') if isinstance(path, str) else path

        if path[0] not in self.children:
            return None

        return self.children[path[0]].find_path(path[1:])  # Recursive call

    def full_path(self) -> str:
        """
        Returns the full path of this node
        """
        if self.name == '' or self.parent is None:
            return ''

        parent_full_path = self.parent.full_path()

        if parent_full_path == '':
            return self.name

        return f'{parent_full_path}/{self.name}'
