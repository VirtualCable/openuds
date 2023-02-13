# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import typing

from uds import models
from uds.core.util.log import (
    REST,
    OWNER_TYPE_AUDIT,
    DEBUG,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)

if typing.TYPE_CHECKING:
    from .handlers import Handler

# This structct allows us to perform the following:
#   If path has ".../providers/[uuid]/..." we will replace uuid with "provider nanme" sourrounded by []
#   If path has ".../services/[uuid]/..." we will replace uuid with "service name" sourrounded by []
#   If path has ".../users/[uuid]/..." we will replace uuid with "user name" sourrounded by []
#   If path has ".../groups/[uuid]/..." we will replace uuid with "group name" sourrounded by []
UUID_REPLACER = (
    ('providers', models.Provider),
    ('services', models.Service),
    ('users', models.User),
    ('groups', models.Group),
)


def replacePath(path: str) -> str:
    """Replaces uuids in path with names
    All paths are in the form .../type/uuid/...
    """
    for type, model in UUID_REPLACER:
        if f'/{type}/' in path:
            try:
                uuid = path.split(f'/{type}/')[1].split('/')[0]
                name = model.objects.get(uuid=uuid).name  # type: ignore
                path = path.replace(uuid, f'[{name}]')
            except Exception:   # nosec: intentionally broad exception
                pass

    return path


def log_operation(
    handler: typing.Optional['Handler'], response_code: int, level: int = INFO
):
    """
    Logs a request
    """
    if not handler:
        return  # Nothing to log

    path = handler._request.path

    # If a common request, and no error, we don't log it because it's useless and a waste of resources
    if response_code < 400 and any(
        x in path for x in ('overview', 'tableinfo', 'gui', 'types', 'system')
    ):
        return

    path = replacePath(path)

    username = handler._request.user.pretty_name if handler._request.user else 'Unknown'
    # Global log is used without owner nor type
    models.Log.objects.create(
        owner_id=0,
        owner_type=OWNER_TYPE_AUDIT,
        created=models.getSqlDatetime(),
        level=level,
        source=REST,
        data=f'{handler._request.ip} {username}: [{handler._request.method}/{response_code}] {path}'[
            :4096
        ],
    )
