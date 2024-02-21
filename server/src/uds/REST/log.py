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
import collections.abc

from uds import models

# Import for REST using this module can access constants easily
# pylint: disable=unused-import
from uds.core.util.log import LogLevel, LogSource, log

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
    ('servicespools', models.ServicePool),
    ('users', models.User),
    ('groups', models.Group),
)


def replace_path(path: str) -> str:
    """Replaces uuids in path with names
    All paths are in the form .../type/uuid/...
    """
    for type, model in UUID_REPLACER:
        if f'/{type}/' in path:
            try:
                uuid = path.split(f'/{type}/')[1].split('/')[0]
                name = model.objects.get(uuid=uuid).name
                path = path.replace(uuid, f'[{name}]')
            except Exception:  # nosec: intentionally broad exception
                pass

    return path


def log_operation(
    handler: typing.Optional['Handler'], response_code: int, level: LogLevel = LogLevel.INFO
) -> None:
    """
    Logs a request
    """
    if not handler:
        return  # Nothing to log

    path = handler.request.path

    # If a common request, and no error, we don't log it because it's useless and a waste of resources
    if response_code < 400 and any(
        x in path for x in ('overview', 'tableinfo', 'gui', 'types', 'system')
    ):
        return

    path = replace_path(path)

    username = handler.request.user.pretty_name if handler.request.user else 'Unknown'
    log(
        None,  # > None Objects goes to SYSLOG (global log)
        level=level,
        message=f'{handler.request.ip} [{username}]: [{handler.request.method}/{response_code}] {path}'[
            :4096
        ],
        source=LogSource.REST,
    )
