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
import datetime
import logging
import random
import typing

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from uds.core import exceptions, types
from uds.core.util import model as model_utils
from uds.core.util import singleton
from uds.core.util.storage import Storage

from .servers_api import request

if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    @property
    def storage(self) -> Storage:
        return Storage('uds.servers')

    def notifyPreconnect(
        self,
        server: 'models.RegisteredServer',
        userService: 'models.UserService',
        info: types.connections.ConnectionInfoType,
    ) -> None:
        """
        Notifies preconnect to server
        """
        request.ServerApiRequester(server).notifyPreconnect(userService, info)

    def notifyRemoval(self, server: 'models.RegisteredServer', userService: 'models.UserService') -> None:
        """
        Notifies removal to server
        """
        request.ServerApiRequester(server).notifyRemoval(userService)

    def processNotification(self, server: 'models.RegisteredServer', data: str) -> None:
        """
        Processes a notification from server
        """
        pass

    def _findBestServer(
        self,
        serverGroup: 'models.RegisteredServerGroup',
        minMemory: int = 0,
        limitLockDate: typing.Optional[datetime.datetime] = None,
    ) -> typing.Tuple['models.RegisteredServer', 'types.servers.ServerStatsType']:
        """
        Finds the best server for a service
        """
        best: typing.Optional[typing.Tuple['models.RegisteredServer', 'types.servers.ServerStatsType']] = None
        unmanaged_list: typing.List['models.RegisteredServer'] = []
        fltrs = serverGroup.servers.filter(maintenance_mode=False)
        if limitLockDate:
            fltrs = fltrs.filter(Q(locked=None) | Q(locked__lt=limitLockDate))  # Only unlocked servers
        else:
            fltrs = fltrs.filter(locked=None)
        for server in fltrs.select_for_update():
            stats = request.ServerApiRequester(server).getStats()
            if stats is None:
                unmanaged_list.append(server)
                continue
            if minMemory and stats.mem < minMemory:
                continue

            if best is None:
                best = (server, stats)
            elif stats.weight() < best[1].weight():
                best = (server, stats)

        # Cannot be assigned to any server!!
        if best is None and len(unmanaged_list) == 0:
            raise exceptions.UDSException(_('No server available for user'))

        # If no best, select one from unmanaged
        if best is None:
            best = (
                random.choice(unmanaged_list),  # nosec: Simple random selection, no security required
                types.servers.ServerStatsType.empty(),
            )

        return best

    def assign(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.RegisteredServerGroup',
        serverType: types.services.ServiceType = types.services.ServiceType.VDI,
        minMemory: int = 0,
        lock: typing.Optional[datetime.timedelta] = None,
        server: typing.Optional['models.RegisteredServer'] = None,
    ) -> str:
        """
        Select a server for an userservice to be assigned to

        Args:
            userService: User service to assign server to
            serverGroup: Server group to select server from
            serverType: Type of service to assign
            minMemory: Minimum memory required for server
            lock: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from serverGroup. (Used on manual assign)
        """
        storage_key = (userService.user.uuid if userService.user else '') + serverGroup.uuid
        now = model_utils.getSqlDatetime()

        uuid_counter: typing.Optional[typing.Tuple[str, int]]
        with self.storage.map() as saved:
            if server:
                saved[storage_key] = (server.uuid, 0)
                uuid_counter = (server.uuid, 0)
            else:
                uuid_counter = saved.get(storage_key)
                if uuid_counter:
                    # If server is in maintenance, data is None in fact
                    if models.RegisteredServer.objects.get(uuid=uuid_counter).maintenance_mode:
                        uuid_counter = None
                        del saved[storage_key]
                # If no cached value, get server assignation
                if uuid_counter is None:
                    with transaction.atomic():
                        best = self._findBestServer(
                            serverGroup=serverGroup,
                            minMemory=minMemory,
                            limitLockDate=now - lock if lock else None,
                        )

                        uuid_counter = (best[0].uuid, 0)
                        if lock:
                            best[0].locked = now
                            best[0].save(update_fields=['locked'])

        # Notify to server
        saved[storage_key] = (uuid_counter[0], uuid_counter[1] + 1)
        bestServer = models.RegisteredServer.objects.get(uuid=uuid_counter)
        # if lock requested, store getSqlDatetime() in locked field
        request.ServerApiRequester(bestServer).notifyAssign(userService, serverType)
        return uuid_counter[0]

    def remove(
        self,
        userService: 'models.UserService',
        serverGroups: 'models.RegisteredServerGroup',
        unlock: bool = False,
    ) -> None:
        """
        Unassigns a server from an user
        """
        storage_key = (userService.user.uuid if userService.user else '') + serverGroups.uuid
        with self.storage.map() as saved:
            uuid_counter: typing.Optional[typing.Tuple[str, int]] = saved.get(storage_key)
            # If no cached value, get server assignation
            if uuid_counter is None:
                return
            if uuid_counter[1] == 1:  # Last one, remove it
                del saved[storage_key]
            else:
                saved[storage_key] = (uuid_counter[0], uuid_counter[1] - 1)
        server = models.RegisteredServer.objects.get(uuid=uuid_counter[0])
        if unlock or uuid_counter[1] == 1:
            server.locked = None  # Ensure server is unlocked if no more users are assigned to it
            server.save(update_fields=['locked'])
        request.ServerApiRequester(server).notifyRemoval(userService)
