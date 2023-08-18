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
import datetime
import random
import typing

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from uds import models
from uds.core import exceptions, types
from uds.core.util import model as model_utils
from uds.core.util import singleton
from uds.core.util.storage import StorageAccess, Storage

from .servers_api import request

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    STORAGE_NAME: typing.Final[str] = 'uds.servers'
    MAX_COUNTERS_AGE: typing.Final[datetime.timedelta] = datetime.timedelta(days=3)
    
    last_counters_clean: datetime.datetime

    def __init__(self):
        self.last_counters_clean = datetime.datetime.now()

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    def svrStorage(self) -> 'StorageAccess':
        return Storage(self.STORAGE_NAME).map(atomic=True, group='servers')

    def cntStorage(self) -> 'StorageAccess':
        # If counters are too old, restart them
        if datetime.datetime.now() - self.last_counters_clean > self.MAX_COUNTERS_AGE:
            self.clearCounters()
        return Storage(self.STORAGE_NAME).map(atomic=True, group='counters')

    def storage_key(
        self, serverGroup: 'models.ServerGroup', user: typing.Optional['models.User']
    ) -> str:
        return (user.uuid if user else '') + serverGroup.uuid

    def clearCounters(self) -> None:
        with self.cntStorage() as counters:
            counters.clear()
        self.last_counters_clean = datetime.datetime.now()
            
    def getUnmanagedUsage(self, uuid: str) -> int:
        uuid = 'c' + uuid
        with self.cntStorage() as counters:
            return counters.get(uuid, 0)

    def decreaseUnmanagedUsage(self, uuid: str, forceReset: bool = False) -> None:
        uuid = 'c' + uuid
        with self.cntStorage() as counters:
            if uuid in counters:
                counters[uuid] -= 1
                if counters[uuid] <= 0 or forceReset:
                    del counters[uuid]
                
    def increaseUnmanagedUsage(self, uuid: str, onlyIfExists: bool = False) -> None:
        uuid = 'c' + uuid
        with self.cntStorage() as counters:
            if not onlyIfExists or uuid in counters:
                counters[uuid] = counters.get(uuid, 0) + 1

    def _findBestServer(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
        now: datetime.datetime,
        minMemoryMB: int = 0,
    ) -> typing.Tuple['models.Server', 'types.servers.ServerStatsType']:
        """
        Finds the best server for a service
        """
        best: typing.Optional[typing.Tuple['models.Server', 'types.servers.ServerStatsType']] = None
        unmanaged_list: typing.List['models.Server'] = []
        fltrs = serverGroup.servers.filter(maintenance_mode=False)
        fltrs = fltrs.filter(Q(locked_until=None) | Q(locked_until__lte=now))  # Only unlocked servers
        for server in fltrs.select_for_update():
            stats = request.ServerApiRequester(server).getStats()
            if stats is None:
                unmanaged_list.append(server)
                continue
            if minMemoryMB and stats.memused // (1024 * 1024) < minMemoryMB:  # Stats has minMemory in bytes
                continue

            if best is None:
                best = (server, stats)
            elif stats.weight() < best[1].weight():
                best = (server, stats)

        # Cannot be assigned to any server!!
        # If no best, select one from unmanaged
        if best is None:
            if len(unmanaged_list) == 0:
                raise exceptions.UDSException(_('No server available for user'))

            # Unmanaged servers are a bit messy. We have to keep track of connected users,
            # But users may disconnect (i.e. on machines without actor) and UDS will not notice it.
            # So we have to provide a way to "reset" the server usage, and this is done by
            # Get counter with less usage
            best_with_counter = sorted(
                [(s, self.getUnmanagedUsage(s.uuid)) for s in unmanaged_list], key=lambda x: x[1]
            )[0]
            # Update counter
            self.increaseUnmanagedUsage(best_with_counter[0].uuid)
            best = (
                best_with_counter[0],
                types.servers.ServerStatsType.empty(),
            )

        # If best was locked, notify it
        if best[0].locked_until is not None:
            request.ServerApiRequester(best[0]).notifyRelease(userService)

        return best

    def assign(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
        serviceType: types.services.ServiceType = types.services.ServiceType.VDI,
        minMemoryMB: int = 0,  # Does not apply to unmanged servers
        lockTime: typing.Optional[datetime.timedelta] = None,
        server: typing.Optional['models.Server'] = None,  # If not note
    ) -> typing.Tuple[str, int]:
        """
        Select a server for an userservice to be assigned to

        Args:
            userService: User service to assign server to
            serverGroup: Server group to select server from
            serverType: Type of service to assign
            minMemoryMB: Minimum memory required for server in MB, does not apply to unmanaged servers
            maxLockTime: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from serverGroup. (Used on manual assign)

        Returns:
            uuid of server assigned
        """
        storage_key = self.storage_key(serverGroup, userService.user)
        now = model_utils.getSqlDatetime()

        with self.svrStorage() as saved:
            uuid_counter: typing.Optional[typing.Tuple[str, int]] = saved[storage_key]
            # If server is forced, and server is part of the group, use it
            if server:
                if server.groups.filter(uuid=serverGroup.uuid).count() == 0:
                    raise exceptions.UDSException(_('Server is not part of the group'))
                elif server.maintenance_mode:
                    raise exceptions.UDSException(_('Server is in maintenance mode'))

                # if server.uuid is stored uuid, increase counter (and counters if exits), else store it
                if uuid_counter and uuid_counter[0] == server.uuid:
                    uuid_counter = (server.uuid, uuid_counter[1] + 1)
                else:
                    saved[storage_key] = (server.uuid, 0)
                    uuid_counter = (server.uuid, 0)

                self.increaseUnmanagedUsage(server.uuid, onlyIfExists=True)
            else:
                if uuid_counter:
                    # If server and it is in maintenance, remove it from saved and use another one
                    if models.Server.objects.get(uuid=uuid_counter[0]).maintenance_mode:
                        uuid_counter = None
                        del saved[storage_key]
                    else:
                        # Increase "local" counters for RR if needed
                        self.increaseUnmanagedUsage(uuid_counter[0], onlyIfExists=True)
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
                        best[0].locked_until = now + lockTime if lockTime else None
                        best[0].save(update_fields=['locked_until'])
                elif lockTime:  # If lockTime is set, update it
                    models.Server.objects.filter(uuid=uuid_counter[0]).update(
                        locked_until=now + lockTime
                    )

        # Notify to server
        # Update counter
        uuid_counter = (uuid_counter[0], uuid_counter[1] + 1)
        saved[storage_key] = uuid_counter
        bestServer = models.Server.objects.get(uuid=uuid_counter[0])

        # Notify assgination in every case, even if reassignation to same server is made
        # This lets the server to keep track, if needed, of multi-assignations
        request.ServerApiRequester(bestServer).notifyAssign(userService, serviceType, uuid_counter[1])
        return uuid_counter

    def release(
        self,
        userService: 'models.UserService',
        serverGroups: 'models.ServerGroup',
        unlock: bool = False,
    ) -> typing.Tuple[str, int]:
        """
        Unassigns a server from an user

        Args:
            userService: User service to unassign server from
            serverGroups: Server group to unassign server from
            unlock: If True, unlock server, even if it has more users assigned to it
        """
        with transaction.atomic():
            storage_key = self.storage_key(serverGroups, userService.user)
            resetCounter = False
            with self.svrStorage() as saved:
                uuid_counter: typing.Optional[typing.Tuple[str, int]] = saved.get(storage_key)
                # If no cached value, get server assignation
                if uuid_counter is None:
                    return ('', 0)
                # Ensure counter is at least 1
                uuid_counter = (uuid_counter[0], max(1, uuid_counter[1]))
                if uuid_counter[1] == 1 or unlock:
                    # Last one, remove it
                    del saved[storage_key]
                else:  # Not last one, just decrement counter
                    saved[storage_key] = (uuid_counter[0], uuid_counter[1] - 1)

            server = models.Server.objects.get(uuid=uuid_counter[0])

            if unlock or uuid_counter[1] == 1:
                server.locked_until = None  # Ensure server is unlocked if no more users are assigned to it
                server.save(update_fields=['locked_until'])

                # Enure server counter is cleaned also, because server is considered "fully released"
                resetCounter = True

            # If unmanaged, decrease usage
            if server.type == types.servers.ServerType.UNMANAGED:
                self.decreaseUnmanagedUsage(server.uuid, forceReset=resetCounter)

            request.ServerApiRequester(server).notifyRelease(userService)

        return (uuid_counter[0], uuid_counter[1] - 1)

    def notifyPreconnect(
        self,
        server: 'models.Server',
        userService: 'models.UserService',
        info: types.connections.ConnectionInfoType,
    ) -> None:
        """
        Notifies preconnect to server
        """
        request.ServerApiRequester(server).notifyPreconnect(userService, info)

    def processNotification(self, server: 'models.Server', data: str) -> None:
        """
        Processes a notification from server
        """
        pass
