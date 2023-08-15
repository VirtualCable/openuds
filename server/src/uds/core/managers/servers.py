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

from uds import models
from uds.core import exceptions, types
from uds.core.util import model as model_utils
from uds.core.util import singleton
from uds.core.util.storage import Storage

from .servers_api import request

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    STORAGE_NAME: typing.Final[str] = 'uds.servers'

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    def storage_key(
        self, serverGroup: 'models.RegisteredServerGroup', user: typing.Optional['models.User']
    ) -> str:
        return (user.uuid if user else '') + serverGroup.uuid

    @property
    def storage(self) -> Storage:
        return Storage(ServerManager.STORAGE_NAME)

    def _findBestServer(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.RegisteredServerGroup',
        now: datetime.datetime,
        minMemoryMB: int = 0,
    ) -> typing.Tuple['models.RegisteredServer', 'types.servers.ServerStatsType']:
        """
        Finds the best server for a service
        """
        best: typing.Optional[typing.Tuple['models.RegisteredServer', 'types.servers.ServerStatsType']] = None
        unmanaged_list: typing.List['models.RegisteredServer'] = []
        fltrs = serverGroup.servers.filter(maintenance_mode=False)
        fltrs = fltrs.filter(Q(locked=None) | Q(locked__lte=now))  # Only unlocked servers
        for server in fltrs.select_for_update():
            stats = request.ServerApiRequester(server).getStats()
            if stats is None:
                unmanaged_list.append(server)
                continue
            if minMemoryMB and stats.mem // (1024 * 1024) < minMemoryMB:  # Stats has minMemory in bytes
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

        # If best was locked, notify it
        if best[0].locked is not None:
            request.ServerApiRequester(best[0]).notifyRelease(userService)

        return best

    def assign(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.RegisteredServerGroup',
        serviceType: types.services.ServiceType = types.services.ServiceType.VDI,
        minMemoryMB: int = 0,
        lockTime: typing.Optional[datetime.timedelta] = None,
        server: typing.Optional['models.RegisteredServer'] = None,  # If not note
    ) -> typing.Tuple[str, int]:
        """
        Select a server for an userservice to be assigned to

        Args:
            userService: User service to assign server to
            serverGroup: Server group to select server from
            serverType: Type of service to assign
            minMemoryMB: Minimum memory required for server in MB
            maxLockTime: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from serverGroup. (Used on manual assign)

        Returns:
            uuid of server assigned
        """
        storage_key = self.storage_key(serverGroup, userService.user)
        now = model_utils.getSqlDatetime()

        with self.storage.map() as saved:
            uuid_counter: typing.Optional[typing.Tuple[str, int]] = saved[storage_key]
            # If server is forced, and server is part of the group, use it
            if server and serverGroup.servers.filter(uuid=server.uuid).exists():
                # if server.uuid is stored uuid, increase counter, else store it
                if uuid_counter and uuid_counter[0] == server.uuid:
                    uuid_counter = (server.uuid, uuid_counter[1] + 1)
                else:
                    saved[storage_key] = (server.uuid, 0)
                    uuid_counter = (server.uuid, 0)
            else:
                # If server and it is in maintenance, remove it from saved and use another one
                if uuid_counter:
                    if models.RegisteredServer.objects.get(uuid=uuid_counter[0]).maintenance_mode:
                        uuid_counter = None
                        del saved[storage_key]
                # If no cached value, get server assignation
                if uuid_counter is None:
                    with transaction.atomic():
                        best = self._findBestServer(
                            userService=userService,
                            serverGroup=serverGroup,
                            now=now,
                            minMemoryMB=minMemoryMB,
                        )

                        uuid_counter = (best[0].uuid, 0)
                        best[0].locked = now + lockTime if lockTime else None
                        best[0].save(update_fields=['locked'])
                elif lockTime:  # If lockTime is set, update it
                    models.RegisteredServer.objects.filter(uuid=uuid_counter[0]).update(
                        locked=now + lockTime
                    )

        # Notify to server
        # Update counter
        uuid_counter = (uuid_counter[0], uuid_counter[1] + 1)
        saved[storage_key] = uuid_counter
        bestServer = models.RegisteredServer.objects.get(uuid=uuid_counter[0])
        # if lock requested, store getSqlDatetime() in locked field
        request.ServerApiRequester(bestServer).notifyAssign(userService, serviceType)
        return uuid_counter

    def release(
        self,
        userService: 'models.UserService',
        serverGroups: 'models.RegisteredServerGroup',
        unlock: bool = False,
    ) -> typing.Optional[typing.Tuple[str, int]]:
        """
        Unassigns a server from an user

        Args:
            userService: User service to unassign server from
            serverGroups: Server group to unassign server from
            unlock: If True, unlock server, even if it has more users assigned to it
        """
        storage_key = self.storage_key(serverGroups, userService.user)

        with self.storage.map() as saved:
            uuid_counter: typing.Optional[typing.Tuple[str, int]] = saved.get(storage_key)
            # If no cached value, get server assignation
            if uuid_counter is None:
                return None
            if uuid_counter[1] == 1:
                # Last one, remove it
                del saved[storage_key]
            elif not unlock:
                # Decrement assignation counter
                saved[storage_key] = (uuid_counter[0], uuid_counter[1] - 1)
            else:
                # Unlock requested, remove assignation even if more users are assigned to it
                del saved[storage_key]

        server = models.RegisteredServer.objects.get(uuid=uuid_counter[0])
        if unlock or uuid_counter[1] == 1:
            server.locked = None  # Ensure server is unlocked if no more users are assigned to it
            server.save(update_fields=['locked'])
        request.ServerApiRequester(server).notifyRelease(userService)

        return (uuid_counter[0], uuid_counter[1] - 1) if uuid_counter[1] > 1 else None

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

    def processNotification(self, server: 'models.RegisteredServer', data: str) -> None:
        """
        Processes a notification from server
        """
        pass
