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
import enum
import logging
import typing

from django import http
from django.shortcuts import render
from django.views.generic.base import View

from uds.core.auths import auth
from uds.core import consts, types

from .dispatcher import Dispatcher

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import types

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class HelpMethodInfo:

    method: str
    text: str
    methods: list[types.rest.doc.HelpNode.Methods]

    def __str__(self) -> str:
        return f'{self.method}: {self.text}'

    def __repr__(self) -> str:
        return self.__str__()


class HelpMethod(enum.Enum):
    ITEM = HelpMethodInfo(
        '<uuid>',
        'Retrieves an item by its UUID',
        [
            types.rest.doc.HelpNode.Methods.GET,
            types.rest.doc.HelpNode.Methods.PUT,
            types.rest.doc.HelpNode.Methods.DELETE,
        ],
    )
    LOG = HelpMethodInfo(
        f'<uuid>/{consts.rest.LOG}',
        'Retrieves the logs of an element by its UUID',
        [
            types.rest.doc.HelpNode.Methods.GET,
        ],
    )
    OVERVIEW = HelpMethodInfo(
        consts.rest.OVERVIEW, 'General Overview of all items (a list)', [types.rest.doc.HelpNode.Methods.GET]
    )
    TABLEINFO = HelpMethodInfo(
        consts.rest.TABLEINFO,
        'Table visualization information (types, etc..)',
        [
            types.rest.doc.HelpNode.Methods.GET,
        ],
    )
    TYPES = HelpMethodInfo(
        consts.rest.TYPES,
        'Retrieves a list of types available',
        [
            types.rest.doc.HelpNode.Methods.GET,
        ],
    )
    TYPES_TYPE = HelpMethodInfo(
        f'{consts.rest.TYPES}/<type>',
        'Retrieves a type information',
        [
            types.rest.doc.HelpNode.Methods.GET,
        ],
    )
    GUI = HelpMethodInfo(consts.rest.GUI, 'GUI information', [types.rest.doc.HelpNode.Methods.GET])
    GUI_TYPES = HelpMethodInfo(
        f'{consts.rest.GUI}/<type>', 'GUI Types information', [types.rest.doc.HelpNode.Methods.GET]
    )


@dataclasses.dataclass(frozen=True)
class HelpInfo:
    path: str
    text: str
    method: types.rest.doc.HelpNode.Methods = types.rest.doc.HelpNode.Methods.GET

    @property
    def is_empty(self) -> bool:
        return not self.path

    def as_dict(self) -> dict[str, str]:
        return {
            'path': self.path,
            'text': self.text,
            'method': self.method.value,
        }


class Documentation(View):

    def dispatch(
        self, request: 'http.request.HttpRequest', *_args: typing.Any, **kwargs: typing.Any
    ) -> 'http.HttpResponse':
        request = typing.cast('types.requests.ExtendedHttpRequest', request)
        if not request.user or not request.authorized:
            return auth.weblogout(request)

        if not request.user.get_role().can_access(consts.UserRole.STAFF):
            return auth.weblogout(request)

        help_data: list[HelpInfo] = []

        def _process_node(node: 'types.rest.doc.HelpNode', path: str) -> None:
            match node.kind:
                case types.rest.doc.HelpNode.Type.PATH:
                    pass
                case types.rest.doc.HelpNode.Type.MODEL | types.rest.doc.HelpNode.Type.DETAIL:
                    for func in [
                        HelpMethod.OVERVIEW,
                        HelpMethod.GUI,
                        HelpMethod.GUI_TYPES,
                        HelpMethod.TYPES,
                        HelpMethod.TYPES_TYPE,
                        HelpMethod.TABLEINFO,
                        HelpMethod.ITEM,
                        HelpMethod.LOG,
                    ]:
                        for method in func.value.methods:
                            help_data.append(HelpInfo(f'{path}/{func.value.method}', func.value.text, method))
                case _:
                    for method in node.methods:
                        help_data.append(HelpInfo(path, node.help.description, method))

            for child in node.children:
                _process_node(child, child.help.path)

        _process_node(Dispatcher.base_handler_node.help_node(), '')

        response = render(
            request=request,
            template_name='uds/modern/documentation.html',
            context={'help': [h.as_dict() for h in help_data]},
        )

        return response

        service = Dispatcher.base_handler_node

        # return http.HttpResponseServerError(f'{service.tree()}', content_type="text/plain")
