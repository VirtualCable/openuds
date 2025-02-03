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

    def __str__(self) -> str:
        return f'{self.method}: {self.text}'

    def __repr__(self) -> str:
        return self.__str__()


class HelpMethod(enum.Enum):
    ITEM = HelpMethodInfo('', 'Retrieves an item by its UUID')
    LOG = HelpMethodInfo(f'<uuid>/{consts.rest.LOG}', 'Retrieves the log of an item')
    OVERVIEW = HelpMethodInfo(consts.rest.OVERVIEW, 'General Overview of all items (a list')
    TABLEINFO = HelpMethodInfo(consts.rest.TABLEINFO, 'Table visualization information (types, etc..)')
    TYPES = HelpMethodInfo(consts.rest.TYPES, 'Retrieves a list of types available')
    TYPES_TYPE = HelpMethodInfo(f'{consts.rest.TYPES}/<type>', 'Retrieves a type information')
    GUI = HelpMethodInfo(consts.rest.GUI, 'GUI information')
    GUI_TYPES = HelpMethodInfo(f'{consts.rest.GUI}/<type>', 'GUI Types information')


@dataclasses.dataclass
class HelpInfo:
    level: int
    path: str
    text: str
    methods: list[HelpMethod]


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

        def _process_node(node: 'types.rest.HelpNode', path: str, level: int) -> None:
            if node.kind == types.rest.HelpNode.HelpNodeType.MODEL:
                methods = [
                    HelpMethod.OVERVIEW,
                    HelpMethod.GUI,
                    HelpMethod.GUI_TYPES,
                    HelpMethod.TYPES,
                    HelpMethod.TYPES_TYPE,
                    HelpMethod.TABLEINFO,
                    HelpMethod.ITEM,
                    HelpMethod.LOG,
                ]
            elif node.kind == types.rest.HelpNode.HelpNodeType.DETAIL:
                methods = [
                    HelpMethod.OVERVIEW,
                    HelpMethod.GUI,
                    HelpMethod.GUI_TYPES,
                    HelpMethod.TYPES,
                    HelpMethod.TYPES_TYPE,
                    HelpMethod.TABLEINFO,
                    HelpMethod.ITEM,
                    HelpMethod.LOG,                    
                ]
            else:
                methods = []

            help_data.append(HelpInfo(level, path, node.help.text, methods))

            for child in node.children:
                _process_node(
                    child,
                    child.help.path,
                    level + (0 if node.kind == types.rest.HelpNode.HelpNodeType.PATH else 1),
                )

        _process_node(Dispatcher.base_handler_node.help_node(), '', 0)

        response = render(
            request=request,
            template_name='uds/modern/documentation.html',
            context={'help': help_data},
        )

        return response

        service = Dispatcher.base_handler_node

        # return http.HttpResponseServerError(f'{service.tree()}', content_type="text/plain")
