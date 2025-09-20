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
from uds.core.util import api as api_utils

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.REST.model.master import ModelHandler

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=models.Model)


def api_paths(
    cls: type['ModelHandler[types.rest.T_Item]'], path: str, tags: list[str], security: str
) -> dict[str, types.rest.api.PathItem]:
    """
    Returns the API operations that should be registered
    """
    
    name = cls.REST_API_INFO.name if cls.REST_API_INFO.name else cls.MODEL.__name__
    get_tags = tags
    put_tags = tags  # + ['Create', 'Modify']
    # post_tags = tags + ['Create']
    delete_tags = tags  # + ['Delete']

    base_type = next(iter(api_utils.get_generic_types(cls)), None)
    if base_type is None:
        logger.error('Base type not detected: %s', cls)
        return {}  # Skip
    else:
        base_type_name = base_type.__name__

    api_desc = {
        path: types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get all {name} items',
                description=f'Retrieve a list of all {name} items',
                parameters=api_utils.gen_odata_parameters(),
                responses=api_utils.gen_response(base_type_name, single=False),
                tags=get_tags,
                security=security,
            ),
            put=types.rest.api.Operation(
                summary=f'Creates a new {name} item',
                description=f'Creates a new, nonexisting {name} item',
                parameters=[],
                requestBody=api_utils.gen_request_body(base_type_name, create=True),
                responses=api_utils.gen_response(base_type_name, with_404=True),
                tags=put_tags,
                security=security,
            ),
        ),
        f'{path}/{{uuid}}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get {name} item by UUID',
                description=f'Retrieve a {name} item by UUID',
                parameters=api_utils.gen_uuid_parameters(with_odata=True),
                responses=api_utils.gen_response(base_type_name, with_404=True),
                tags=get_tags,
                security=security,
            ),
            put=types.rest.api.Operation(
                summary=f'Update {name} item by UUID',
                description=f'Update an existing {name} item by UUID',
                parameters=api_utils.gen_uuid_parameters(with_odata=False),
                responses=api_utils.gen_response(base_type_name, with_404=True),
                tags=put_tags,
                security=security,
            ),
            delete=types.rest.api.Operation(
                summary=f'Delete {name} item by UUID',
                description=f'Delete a {name} item by UUID',
                parameters=api_utils.gen_uuid_parameters(with_odata=False),
                responses=api_utils.gen_response(base_type_name, with_404=True),
                tags=delete_tags,
                security=security,
            ),
        ),
        f'{path}/{consts.rest.OVERVIEW}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get overview of {name} items',
                description=f'Retrieve an overview of {name} items',
                parameters=api_utils.gen_odata_parameters(),
                responses=api_utils.gen_response(base_type_name, single=False),
                tags=get_tags,
                security=security,
            )
        ),
        f'{path}/{consts.rest.TABLEINFO}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get table info of {name} items',
                description=f'Retrieve table info of {name} items',
                parameters=[],
                responses=api_utils.gen_response('TableInfo', with_404=True),
                tags=get_tags,
                security=security,
            )
        ),
        f'{path}/{consts.rest.TYPES}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get types of {name} items',
                description=f'Retrieve types of {name} items',
                parameters=[],
                responses=api_utils.gen_response(base_type_name, single=False),
                tags=get_tags,
                security=security,
            )
        ),
        f'{path}/{consts.rest.TYPES}/{{type}}': types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get {name} item by type',
                description=f'Retrieve a {name} item by type',
                parameters=[
                    types.rest.api.Parameter(
                        name='type',
                        in_='path',
                        required=True,
                        description='The type of the item',
                        schema=types.rest.api.Schema(type='string'),
                    )
                ],
                responses=api_utils.gen_response(base_type_name, with_404=True),
                tags=get_tags,
                security=security,
            )
        ),
    }
    if cls.REST_API_INFO.gui_type.is_untyped():
        api_desc[f'{path}/{consts.rest.GUI}'] = types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get GUI representation of {name} items',
                description=f'Retrieve the GUI representation of {name} items',
                parameters=[],
                responses=api_utils.gen_response('GuiElement', single=False, with_404=True),
                tags=get_tags,
                security=security,
            )
        )

    if cls.REST_API_INFO.gui_type.is_typed():
        api_desc[f'{path}/{consts.rest.GUI}/{{type}}'] = types.rest.api.PathItem(
            get=types.rest.api.Operation(
                summary=f'Get GUI representation of {name} type',
                description=f'Retrieve a {name} GUI representation by type',
                parameters=[
                    types.rest.api.Parameter(
                        name='type',
                        in_='path',
                        required=True,
                        description=f'The type of the {name} GUI representation',
                        schema=types.rest.api.Schema(type='string'),
                    )
                ],
                responses=api_utils.gen_response('GuiElement', single=False, with_404=True),
                tags=get_tags,
                security=security,
            )
        )

    return api_desc
