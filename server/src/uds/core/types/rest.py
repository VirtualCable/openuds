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
import abc
import enum
import re
import typing
import dataclasses
import collections.abc

if typing.TYPE_CHECKING:
    from uds.REST.handlers import Handler


TypeInfoDict = dict[str, typing.Any]  # Alias for type info dict


class ExtraTypeInfo(abc.ABC):
    def as_dict(self) -> TypeInfoDict:
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
    mfa_supported: bool

    def as_dict(self) -> TypeInfoDict:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class TypeInfo:
    name: str
    type: str
    description: str
    icon: str

    group: typing.Optional[str] = None

    extra: 'ExtraTypeInfo|None' = None

    def as_dict(self) -> TypeInfoDict:
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


# This is a named tuple for convenience, and must be
# compatible with tuple[str, bool] (name, needs_parent)
@dataclasses.dataclass
class ModelCustomMethod:
    name: str
    needs_parent: bool = True


# Alias for item type
ItemDictType = dict[str, typing.Any]
ItemListType = list[ItemDictType]
ItemGeneratorType = typing.Generator[ItemDictType, None, None]

# Alias for get_items return type
ManyItemsDictType = typing.Union[ItemListType, ItemDictType, ItemGeneratorType]

#
FieldType = collections.abc.Mapping[str, typing.Any]

# Regular expression to match the API: part of the docstring
# should be a multi line string, with a line containing only "API:" (with leading and trailing \s)
API_RE = re.compile(r'(?ms)^\s*API:\s*$')


@dataclasses.dataclass(eq=False)
class HelpPath:
    """
    Help helper class
    """

    path: str
    text: str

    def __init__(self, path: str, help: str):
        self.path = path
        self.text = HelpPath.process_help(help)

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HelpPath):
            return False
        return self.path == other.path

    @property
    def is_empty(self) -> bool:
        return self.path == '' and self.text == ''

    @staticmethod
    def process_help(help: str) -> str:
        """
        Processes the help string, removing leading and trailing spaces
        """
        match = API_RE.search(help)
        if match:
            return help[match.end() :].strip()

        return ''


@dataclasses.dataclass(frozen=True)
class HelpNode:
    class HelpNodeType(enum.StrEnum):
        MODEL = 'model'
        DETAIL = 'detail'
        CUSTOM = 'custom'
        PATH = 'path'

    help: HelpPath
    children: list['HelpNode']  # Children nodes
    kind: HelpNodeType

    def __hash__(self) -> int:
        return hash(self.help.path)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HelpNode):
            return self.help.path == other.help.path
        if not isinstance(other, HelpPath):
            return False

        return self.help.path == other.path

    @property
    def is_empty(self) -> bool:
        return self.help.is_empty and not self.children

    def __str__(self) -> str:
        return f'HelpNode({self.help}, {self.children})'


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
            # Add custom_methods
            for method in self.handler.custom_methods:
                ret += f'{"  " * level}  |- {method}\n'
            # Add detail methods
            if self.handler.detail:
                for method in self.handler.detail.keys():
                    ret += f'{"  " * level}  |- {method}\n'

        return ret + ''.join(child.tree(level + 1) for child in self.children.values())

    def help_node(self) -> HelpNode:
        """
        Returns a HelpNode for this node (and children recursively)
        """
        from uds.REST.model import ModelHandler

        custom_help: set[HelpNode] = set()

        help_node_type = HelpNode.HelpNodeType.PATH

        if self.handler:
            help_node_type = HelpNode.HelpNodeType.CUSTOM
            if issubclass(self.handler, ModelHandler):
                help_node_type = HelpNode.HelpNodeType.MODEL
                # Add custom_methods
                for method in self.handler.custom_methods:
                    # Method is a Me CustomModelMethod,
                    # We access the __doc__ of the function inside the handler with method.name
                    doc = getattr(self.handler, method.name).__doc__ or ''
                    custom_help.add(
                        HelpNode(
                            HelpPath(path=self.full_path() + '/' + method.name, help=doc),
                            [],
                            HelpNode.HelpNodeType.CUSTOM,
                        )
                    )

                # Add detail methods
                if self.handler.detail:
                    for method_name, method_class in self.handler.detail.items():
                        custom_help.add(
                            HelpNode(
                                HelpPath(path=self.full_path() + '/' + method_name, help=''),
                                [],
                                HelpNode.HelpNodeType.DETAIL,
                            )
                        )
                        # Add custom_methods
                        for detail_method in method_class.custom_methods:
                            # Method is a Me CustomModelMethod,
                            # We access the __doc__ of the function inside the handler with method.name
                            doc = getattr(method_class, detail_method).__doc__ or ''
                            custom_help.add(
                                HelpNode(
                                    HelpPath(path=self.full_path() + '/<uuid>/' + method_name + '/<uuid>/' + detail_method, help=doc),
                                    [],
                                    HelpNode.HelpNodeType.CUSTOM,
                                )
                            )

            custom_help |= {
                HelpNode(HelpPath(path=help_info.path, help=help_info.text), [], help_node_type)
                for help_info in self.handler.help_paths
            }

        custom_help |= {child.help_node() for child in self.children.values()}

        return HelpNode(
            help=HelpPath(path=self.full_path(), help=self.handler.__doc__ or ''),
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
