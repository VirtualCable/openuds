# -*- coding: utf-8 -*-

#
# Copyright (c) 2021 Virtual Cable S.L.U.
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
import datetime
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds.core import types, consts
from uds.core.types import permissions
from uds.core.util import ensure, ui as ui_utils
from uds.core.util.log import LogLevel
from uds.models import Server
from uds.core.exceptions.rest import NotFound, RequestError
from uds.REST.model import ModelHandler

if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Enclosed methods under /osm path

@dataclasses.dataclass
class ActorTokenItem(types.rest.BaseRestItem):
    id: str
    name: str
    stamp: datetime.datetime
    username: str
    ip: str
    host: str
    hostname: str
    version: str
    pre_command: str
    post_command: str
    run_once_command: str
    log_level: str
    os: str


class ActorTokens(ModelHandler[ActorTokenItem]):

    MODEL = Server
    FILTER = {'type': types.servers.ServerType.ACTOR}

    TABLE = (
        ui_utils.TableBuilder(_('Actor tokens'))
        .datetime_column('stamp', _('Date'))
        .text_column('username', _('Issued by'))
        .text_column('host', _('Origin'))
        .text_column('version', _('Version'))
        .text_column('hostname', _('Hostname'))
        .text_column('pre_command', _('Pre-connect'))
        .text_column('post_command', _('Post-Configure'))
        .text_column('run_once_command', _('Run Once'))
        .text_column('log_level', _('Log level'))
        .text_column('os', _('OS'))
        .build()
    )

    def get_item(self, item: 'Model') -> ActorTokenItem:
        item = ensure.is_instance(item, Server)
        data: dict[str, typing.Any] = item.data or {}
        if item.log_level < 10000:  # Old log level, from actor, etc..
            log_level = LogLevel.from_actor_level(item.log_level).name
        else:
            log_level = LogLevel(item.log_level).name
        return ActorTokenItem(
            id=item.token,
            name=str(_('Token isued by {} from {}')).format(
                item.register_username, item.hostname or item.ip
            ),
            stamp=item.stamp,
            username=item.register_username,
            ip=item.ip,
            host=f'{item.ip} - {data.get("mac")}',
            hostname=item.hostname,
            version=item.version,
            pre_command=data.get('pre_command', ''),
            post_command=data.get('post_command', ''),
            run_once_command=data.get('run_once_command', ''),
            log_level=log_level,
            os=item.os_type,
        )

    def delete(self) -> str:
        """
        Processes a DELETE request
        """
        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')

        self.check_access(
            self.MODEL(), permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            self.MODEL.objects.get(token=self._args[0]).delete()
        except self.MODEL.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return consts.OK
