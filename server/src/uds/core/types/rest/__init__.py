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
import typing
import dataclasses

from . import doc
from . import stock

if typing.TYPE_CHECKING:
    from uds.REST.handlers import Handler
    from uds.core import types


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


# This is a named tuple for convenience, and must be
# compatible with tuple[str, bool] (name, needs_parent)
@dataclasses.dataclass
class ModelCustomMethod:
    name: str
    needs_parent: bool = True


# Note that for this item to work with documentation
# no forward references can be used (that is, do not use quotes around the inner field types)
class BaseRestItem(typing.TypedDict):
    pass


class ManagedObjectItem(BaseRestItem):
    """
    Represents a managed object type, with its name and type.
    This is used to represent the type of a managed object in the REST API.
    """

    type: typing.NotRequired[str]  # Type of the managed object
    type_name: typing.NotRequired[str]  # Name of the type of the managed object
    instance: typing.NotRequired[typing.Any]  # Instance of the managed object, if available


# Alias for item type
T_Item = typing.TypeVar("T_Item", bound=BaseRestItem)

# Alias for get_items return type
ItemsResult: typing.TypeAlias = list[T_Item] | BaseRestItem | typing.Iterator[T_Item]


@dataclasses.dataclass
class TableInfo:
    """
    Represents the table info for a REST API endpoint.
    This is used to describe the table fields and row style.
    """

    title: str
    fields: list[dict[str, dict[str, typing.Any]]]
    row_style: 'types.ui.RowStyleInfo'
    subtitle: typing.Optional[str] = None

    def as_dict(self) -> dict[str, typing.Any]:
        return {
            'title': self.title,
            'fields': self.fields,
            'row-style': self.row_style.as_dict(),
            'subtitle': self.subtitle or '',
        }


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
            for method in handler.custom_methods:
                ret += f'{"  " * level}  |- {method}\n'
            # Add detail methods
            if handler.detail:
                for method_name in handler.detail.keys():
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
                [],
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
            for method in handler.custom_methods:
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
            if handler.detail:
                for method_name, method_class in handler.detail.items():
                    custom_help.add(
                        doc.HelpNode(
                            doc.HelpDoc(path=self.full_path() + '/' + method_name, help=''),
                            [],
                            doc.HelpNode.Type.DETAIL,
                        )
                    )
                    # Add custom_methods
                    for detail_method in method_class.custom_methods:
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
                for help_info in handler.help_paths
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
