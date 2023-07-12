# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import enum

from django.db import models
from uds.core.util.request import ExtendedHttpRequest

from .consts import MAX_DNS_NAME_LENGTH, MAX_IPV6_LENGTH

class RegisteredServers(models.Model):
    """
    UDS Registered Servers

    This table stores the information about registered servers for tunnel servers (on v3.6) or
    more recently, for other kind of servers that may be need to be registered (as app servers)

    kind field is a flag that indicates the kind of server that is registered. This is used to
    allow or deny access to the API for this server.
    Currently there are two kinds of servers:
    - Tunnel servers: This is the original use of this table, and is used to allow tunnel servers (1)
    - Other servers: This is used to register server that needs to access some API methods, but
        that are not tunnel servers (2)

    If server is Other, but not Tunnel, it will be allowed to access API, but will not be able to
    create tunnels.
    """
    class ServerType(enum.IntFlag):
        TUNNEL = 1
        OTHER = 2

        def as_str(self) -> str:
            return self.name.lower()  # type: ignore

    username = models.CharField(max_length=128)
    ip_from = models.CharField(max_length=MAX_IPV6_LENGTH)
    ip = models.CharField(max_length=MAX_IPV6_LENGTH)
    hostname = models.CharField(max_length=MAX_DNS_NAME_LENGTH)

    token = models.CharField(max_length=48, db_index=True, unique=True)
    stamp = models.DateTimeField()  # Date creation or validation of this entry

    kind = models.IntegerField(default=ServerType.TUNNEL.value)  # Defaults to tunnel server, so we can migrate from previous versions

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[TunnelToken]'

    class Meta:  # pylint: disable=too-few-public-methods
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(fields=['ip', 'hostname'], name='tt_ip_hostname')
        ]

    @staticmethod
    def validateToken(
        token: str, request: typing.Optional[ExtendedHttpRequest] = None
    ) -> bool:
        try:
            tt = RegisteredServers.objects.get(token=token)
            # We could check the request ip here
            if request and request.ip != tt.ip:
                raise Exception('Invalid ip')
            return True
        except RegisteredServers.DoesNotExist:
            pass
        return False

    def __str__(self):
        return f'<TunnelToken {self.token} created on {self.stamp} by {self.username} from {self.ip}/{self.hostname}>'
