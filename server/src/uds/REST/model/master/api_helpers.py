# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.U.
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
# pylint: disable=too-many-public-methods

import logging
import typing

from django.db import models
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core import types


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.REST.model.master import ModelHandler

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=models.Model)


def api_paths(
    klass: type['ModelHandler[types.rest.T_Item]'], path: str
) -> dict[str, types.rest.api.PathItem]:
    """
    Returns the API operations that should be registered
    """
    # The the base path
    return {
        path: types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get all {klass.MODEL.__name__} items',
                description=f'Retrieve a list of all {klass.MODEL.__name__} items',
                parameters=[],
                responses={},
            ),
            put=types.rest.api.Operation(
                summary=f'Creates or Update {klass.MODEL.__name__} items',
                description=f'Update an existing {klass.MODEL.__name__} item',
                parameters=[],
                responses={},
            ),
            # To be implemented in future, allow PUT for update, POST for new items
            # post=types.rest.api.Operation(
            #     summary=f'Creates a new {cls.MODEL.__name__} item',
            #     description=f'Create a new {cls.MODEL.__name__} item',
            #     parameters=[],
            #     responses={},
            # )
            delete=types.rest.api.Operation(
                summary=f'Delete {klass.MODEL.__name__} items',
                description=f'Delete an existing {klass.MODEL.__name__} item',
                parameters=[],
                responses={},
            ),
        ),
        f'{path}{consts.rest.OVERVIEW}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get overview of {klass.MODEL.__name__} items',
                description=f'Retrieve an overview of {klass.MODEL.__name__} items',
                parameters=[],
                responses={},
            )
        ),
        f'{path}{consts.rest.TABLEINFO}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get table info of {klass.MODEL.__name__} items',
                description=f'Retrieve table info of {klass.MODEL.__name__} items',
                parameters=[],
                responses={},
            )
        ),
        f'{path}{consts.rest.TYPES}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get types of {klass.MODEL.__name__} items',
                description=f'Retrieve types of {klass.MODEL.__name__} items',
                parameters=[],
                responses={},
            )
        ),
        f'{path}/{consts.rest.TYPES}/{{type}}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get {klass.MODEL.__name__} item by type',
                description=f'Retrieve a {klass.MODEL.__name__} item by type',
                parameters=[
                    types.rest.api.Parameter(
                        name='type',
                        in_='path',
                        required=True,
                        description='The type of the item',
                        schema=types.rest.api.Schema(type='string'),
                    )
                ],
                responses={},
            )
        ),
        f'{path}{consts.rest.GUI}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get GUI representation of {klass.MODEL.__name__} items',
                description=f'Retrieve the GUI representation of {klass.MODEL.__name__} items',
                parameters=[],
                responses={},
            )
        ),
        f'{path}{consts.rest.GUI}/{{type}}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get {klass.MODEL.__name__} item by type',
                description=f'Retrieve a {klass.MODEL.__name__} item by type',
                parameters=[
                    types.rest.api.Parameter(
                        name='type',
                        in_='path',
                        required=True,
                        description='The type of the item',
                        schema=types.rest.api.Schema(type='string'),
                    )
                ],
                responses={},
            )
        ),
    }
