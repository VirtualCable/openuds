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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_lazy as _

from uds.models import ActorToken
from uds.REST.exceptions import RequestError, NotFound
from uds.REST.model import ModelHandler, OK
from uds.core.util import permissions
from uds.core.util.log import LogLevel

logger = logging.getLogger(__name__)

# Enclosed methods under /osm path


class ActorTokens(ModelHandler):
    model = ActorToken

    table_title = _('Actor tokens')
    table_fields = [
        # {'token': {'title': _('Token')}},
        {'stamp': {'title': _('Date'), 'type': 'datetime'}},
        {'username': {'title': _('Issued by')}},
        {'host': {'title': _('Origin')}},
        {'hostname': {'title': _('Hostname')}},
        {'pre_command': {'title': _('Pre-connect')}},
        {'post_command': {'title': _('Post-Configure')}},
        {'runonce_command': {'title': _('Run Once')}},
        {'log_level': {'title': _('Log level')}},
    ]

    def item_as_dict(self, item: ActorToken) -> typing.Dict[str, typing.Any]:
        return {
            'id': item.token,
            'name': str(_('Token isued by {} from {}')).format(
                item.username, item.hostname or item.ip
            ),
            'stamp': item.stamp,
            'username': item.username,
            'ip': item.ip,
            'host': f'{item.ip} - {item.mac}',
            'hostname': item.hostname,
            'pre_command': item.pre_command,
            'post_command': item.post_command,
            'runonce_command': item.runonce_command,
            'log_level': LogLevel.fromActorLevel(item.log_level).name  # ['DEBUG', 'INFO', 'ERROR', 'FATAL'][item.log_level % 4],
        }

    def delete(self) -> str:
        """
        Processes a DELETE request
        """
        if len(self._args) != 1:
            raise RequestError('Delete need one and only one argument')

        self.ensureAccess(
            self.model(), permissions.PermissionType.ALL, root=True
        )  # Must have write permissions to delete

        try:
            self.model.objects.get(token=self._args[0]).delete()
        except self.model.DoesNotExist:
            raise NotFound('Element do not exists') from None

        return OK
