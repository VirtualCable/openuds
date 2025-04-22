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
import enum
import re
import typing
import dataclasses
import collections.abc


# TypedResponse related.
# Typed responses are used to define the type of the response that a method will return.
# This allow us to "describe" it later on the documentation, and also to check that the
# response is correct (and also to generate the response in the correct format)
class TypedResponse(typing.TypedDict):
    pass

def extract_doc(response: type[TypedResponse]) -> dict[str, typing.Any]:
    """
    Returns a representation, as json, of the response type to be used on documentation

    For this, we build a dict of "name": "<type>" for each field of the response and returns it
    Note that we support nested dataclasses and dicts, but not lists
    """
    CLASS_REPR: dict[typing.Any, str] = {
        str: '<string>',
        int: '<integer>',
        float: '<float>',
        bool: '<boolean>',
        dict: '<dict>',
        list: '<list>',
        typing.Any: '<any>',
    }

    def _as_help(obj: typing.Any) -> typing.Union[str, dict[str, typing.Any]]:
        if hasattr(obj, '__annotations__'):
            return {name: _as_help(field) for name, field in obj.__annotations__.items()}

        return CLASS_REPR.get(obj, str(obj))

    # For sure, first level is a dict
    return typing.cast(dict[str, typing.Any], _as_help(response))


def is_typed_response(t: type[TypedResponse]) -> bool:
    return hasattr(t, '__orig_bases__') and TypedResponse in t.__orig_bases__


# Regular expression to match the API: part of the docstring
# should be a multi line string, with a line containing only "API:" (with leading and trailing \s)
API_RE = re.compile(r'(?ms)^\s*API:\s*$')


@dataclasses.dataclass(eq=False)
class HelpDoc:
    """
    Help helper class
    """

    @dataclasses.dataclass
    class ArgumentInfo:
        name: str
        type: str
        description: str

    path: str
    description: str
    arguments: list[ArgumentInfo] = dataclasses.field(default_factory=list[ArgumentInfo])
    # Result is always a json ressponse, so we can describe it as a dict
    # Note that this dict can be nested
    returns: typing.Any = None

    def __init__(
        self,
        path: str,
        help: str,
        *,
        arguments: typing.Optional[list[ArgumentInfo]] = None,
        returns: typing.Optional[dict[str, typing.Any]] = None,
    ) -> None:
        self.path = path
        self.description = help
        self.arguments = arguments or []
        self.returns = returns or {}

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HelpDoc):
            return False
        return self.path == other.path

    def as_str(self) -> str:
        return f'{self.path} - {self.description}'

    @property
    def is_empty(self) -> bool:
        return self.path == '' and self.description == ''

    def _process_help(self, help: str, annotations: typing.Optional[dict[str, typing.Any]] = None) -> None:
        """
        Processes the help string, removing leading and trailing spaces
        """
        self.description = ''
        self.arguments = []
        self.returns = None

        match = API_RE.search(help)
        if match:
            self.description = help[: match.start()].strip()

            if annotations:
                if 'return' in annotations:
                    t = annotations['return']
                    if isinstance(t, collections.abc.Iterable):
                        pass
                    # if issubclass(annotations['return'], TypedResponse):
                    # self.returns = annotations['return'].as_help()

    @staticmethod
    def from_typed_response(path: str, help: str, TR: type[TypedResponse]) -> 'HelpDoc':
        """
        Returns a HelpDoc from a TypedResponse class
        """
        return HelpDoc(
            path=path,
            help=help,
            returns=extract_doc(TR),
        )

    @staticmethod
    def from_fnc(path: str, help: str, fnc: typing.Callable[..., typing.Any]) -> 'HelpDoc|None':
        """
        Returns a HelpDoc from a function that returns a list of TypedResponses
        """
        return_type: typing.Any = fnc.__annotations__.get('return')
        
        if is_typed_response(return_type):
            return HelpDoc.from_typed_response(path, help, typing.cast(type[TypedResponse], return_type))
        elif (
            isinstance(return_type, collections.abc.Iterable)
            and len(typing.get_args(return_type)) == 1
            and is_typed_response(typing.get_args(return_type)[0])
        ):
            hd = HelpDoc.from_typed_response(
                path, help, typing.cast(type[TypedResponse], typing.cast(typing.Any, return_type).__args__[0])
            )
            hd.returns = [hd.returns]  # We need to return a list of returns
            return hd
        
        return None


@dataclasses.dataclass(frozen=True)
class HelpNode:
    class Type(enum.StrEnum):
        MODEL = 'model'
        DETAIL = 'detail'
        CUSTOM = 'custom'
        PATH = 'path'

    class Methods(enum.StrEnum):
        GET = 'GET'
        POST = 'POST'
        PUT = 'PUT'
        DELETE = 'DELETE'
        PATCH = 'PATCH'

    help: HelpDoc
    children: list['HelpNode']  # Children nodes
    kind: Type
    methods: set[Methods] = dataclasses.field(default_factory=lambda: {HelpNode.Methods.GET})

    def __hash__(self) -> int:
        return hash(self.help.path + ''.join(method for method in self.methods))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, HelpNode):
            return self.help.path == other.help.path and self.methods == other.methods
        if not isinstance(other, HelpDoc):
            return False

        return self.help.path == other.path

    @property
    def is_empty(self) -> bool:
        return self.help.is_empty and not self.children

    def __str__(self) -> str:
        return f'HelpNode({self.help}, {self.children})'

