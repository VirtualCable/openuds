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
import typing
from concurrent.futures import ThreadPoolExecutor

from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from uds import models
from uds.core import exceptions, types
from uds.core.util import model as model_utils
from uds.core.util import singleton
from uds.core.util.storage import StorageAccess, Storage

from .servers_api import events, requester

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    STORAGE_NAME: typing.Final[str] = 'uds.servers'
    MAX_COUNTERS_AGE: typing.Final[datetime.timedelta] = datetime.timedelta(days=3)
    PROPERTY_BASE_NAME: typing.Final[str] = 'usr_'

    last_counters_clean: datetime.datetime

    def __init__(self):
        self.last_counters_clean = datetime.datetime.now()

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    def cntStorage(self) -> 'StorageAccess':
        # If counters are too old, restart them
        if datetime.datetime.now() - self.last_counters_clean > self.MAX_COUNTERS_AGE:
            self.clearUnmanagedUsage()
        return Storage(self.STORAGE_NAME).map(atomic=True, group='counters')

    def propertyName(self, user: typing.Optional['models.User']) -> str:
        """Returns the property name for a user"""
        return ServerManager.PROPERTY_BASE_NAME + (str(user.uuid) if user else '_')

    def clearUnmanagedUsage(self) -> None:
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
        excludeServersUUids: typing.Optional[typing.Set[str]] = None,
    ) -> typing.Tuple['models.Server', 'types.servers.ServerStatsType']:
        """
        Finds the best server for a service
        """
        best: typing.Optional[typing.Tuple['models.Server', 'types.servers.ServerStatsType']] = None
        unmanaged_list: typing.List['models.Server'] = []
        fltrs = serverGroup.servers.filter(maintenance_mode=False)
        fltrs = fltrs.filter(Q(locked_until=None) | Q(locked_until__lte=now))  # Only unlocked servers
        if excludeServersUUids:
            fltrs = fltrs.exclude(uuid__in=excludeServersUUids)

        # Paralelize stats retrieval
        cachedStats: typing.List[
            typing.Tuple[typing.Optional['types.servers.ServerStatsType'], 'models.Server']
        ] = []

        def _retrieveStats(server: 'models.Server') -> None:
            try:
                cachedStats.append(
                    (requester.ServerApiRequester(server).getStats(), server)
                )  # Store stats for later use
            except Exception:
                cachedStats.append((None, server))

        with ThreadPoolExecutor(max_workers=10) as executor:
            for server in fltrs.select_for_update():
                executor.submit(_retrieveStats, server)

        # Now, cachedStats has a list of tuples (stats, server), use it to find the best server
        for stats, server in cachedStats:
            if stats is None:
                unmanaged_list.append(server)
                continue
            if minMemoryMB and stats.memused // (1024 * 1024) < minMemoryMB:  # Stats has minMemory in bytes
                continue

            if best is None or stats.weight() < best[1].weight():
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

        # If best was locked, notify it (will be notified again on assign)
        if best[0].locked_until is not None:
            requester.ServerApiRequester(best[0]).notifyRelease(userService)

        return best

    def assign(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
        serviceType: types.services.ServiceType = types.services.ServiceType.VDI,
        minMemoryMB: int = 0,  # Does not apply to unmanged servers
        lockTime: typing.Optional[datetime.timedelta] = None,
        server: typing.Optional['models.Server'] = None,  # If not note
        excludeServersUUids: typing.Optional[typing.Set[str]] = None,
    ) -> typing.Optional[types.servers.ServerCounterType]:
        """
        Select a server for an userservice to be assigned to

        Args:
            userService: User service to assign server to (in fact, user of userservice) and to notify
            serverGroup: Server group to select server from
            serverType: Type of service to assign
            minMemoryMB: Minimum memory required for server in MB, does not apply to unmanaged servers
            maxLockTime: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from serverGroup. (Used on manual assign)
            excludeServersUUids: If not None, exclude this servers from selection. Used in case we check the availability of a server
                                 with some external method and we want to exclude it from selection because it has already failed.

        Returns:
            uuid of server assigned
        """
        if not userService.user:
            raise exceptions.UDSException(_('No user assigned to service'))

        # Look for existint user asignation through properties
        prop_name = self.propertyName(userService.user)
        now = model_utils.getSqlDatetime()

        excludeServersUUids = excludeServersUUids or set()

        with serverGroup.properties as props:
            info: typing.Optional[
                types.servers.ServerCounterType
            ] = types.servers.ServerCounterType.fromIterable(props.get(prop_name))
            # If server is forced, and server is part of the group, use it
            if server:
                if (
                    server.groups.filter(uuid=serverGroup.uuid).exclude(uuid__in=excludeServersUUids).count()
                    == 0
                ):
                    raise exceptions.UDSException(_('Server is not part of the group'))
                elif server.maintenance_mode:
                    raise exceptions.UDSException(_('Server is in maintenance mode'))

                # if server.uuid is stored uuid, increase counter (and counters if exits), else store it
                if info and info.server_uuid == server.uuid:
                    info = types.servers.ServerCounterType(server.uuid, info.counter + 1)
                else:
                    props[prop_name] = (server.uuid, 0)
                    info = types.servers.ServerCounterType(server.uuid, 0)

                self.increaseUnmanagedUsage(server.uuid, onlyIfExists=True)
            else:
                if info and info.server_uuid:
                    # If server does not exists, or it is in maintenance, or it is in exclude list,
                    # remove it from saved and use look for another one
                    svr = models.Server.objects.filter(uuid=info.server_uuid).first()
                    if not svr or (svr.maintenance_mode or svr.uuid in excludeServersUUids):
                        info = None
                        del props[prop_name]
                    else:
                        # Increase "local" counters for RR if needed
                        self.increaseUnmanagedUsage(info.server_uuid, onlyIfExists=True)
                # If no existing assignation, check for a new one
                if info is None:
                    try:
                        with transaction.atomic():
                            best = self._findBestServer(
                                userService=userService,
                                serverGroup=serverGroup,
                                now=now,
                                minMemoryMB=minMemoryMB,
                                excludeServersUUids=excludeServersUUids,
                            )

                            info = types.servers.ServerCounterType(best[0].uuid, 0)
                            best[0].locked_until = now + lockTime if lockTime else None
                            best[0].save(update_fields=['locked_until'])
                    except exceptions.UDSException:  # No more servers
                        return None
                elif lockTime:  # If lockTime is set, update it
                    models.Server.objects.filter(uuid=info[0]).update(locked_until=now + lockTime)

            # Notify to server
            # Update counter
            info = types.servers.ServerCounterType(info.server_uuid, info.counter + 1)
            props[prop_name] = info
            bestServer = models.Server.objects.get(uuid=info.server_uuid)

        # Notify assgination in every case, even if reassignation to same server is made
        # This lets the server to keep track, if needed, of multi-assignations
        requester.ServerApiRequester(bestServer).notifyAssign(userService, serviceType, info.counter)
        return info

    def release(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
        unlock: bool = False,
        userUuid: typing.Optional[str] = None,
    ) -> types.servers.ServerCounterType:
        """
        Unassigns a server from an user

        Args:
            userService: User service to unassign server from
            serverGroups: Server group to unassign server from
            unlock: If True, unlock server, even if it has more users assigned to it
            userUuid: If not None, use this uuid instead of userService.user.uuid
        """
        userUuid = userUuid if userUuid else userService.user.uuid if userService.user else None

        if userUuid is None:
            return types.servers.ServerCounterType.empty()  # No user is assigned to this service, nothing to do

        prop_name = self.propertyName(userService.user)
        with serverGroup.properties as props:
            with transaction.atomic():
                resetCounter = False
                # ServerCounterType

                serverCounter: typing.Optional[
                    types.servers.ServerCounterType
                ] = types.servers.ServerCounterType.fromIterable(props.get(prop_name))
                # If no cached value, get server assignation
                if serverCounter is None:
                    return types.servers.ServerCounterType.empty()
                # Ensure counter is at least 1
                serverCounter = types.servers.ServerCounterType(
                    serverCounter.server_uuid, max(1, serverCounter.counter)
                )
                if serverCounter.counter == 1 or unlock:
                    # Last one, remove it
                    del props[prop_name]
                else:  # Not last one, just decrement counter
                    props[prop_name] = (serverCounter.server_uuid, serverCounter.counter - 1)

            server = models.Server.objects.get(uuid=serverCounter[0])

            if unlock or serverCounter.counter == 1:
                server.locked_until = None  # Ensure server is unlocked if no more users are assigned to it
                server.save(update_fields=['locked_until'])

                # Enure server counter is cleaned also, because server is considered "fully released"
                resetCounter = True

            # If unmanaged, decrease usage
            if server.type == types.servers.ServerType.UNMANAGED:
                self.decreaseUnmanagedUsage(server.uuid, forceReset=resetCounter)

            requester.ServerApiRequester(server).notifyRelease(userService)

        return types.servers.ServerCounterType(serverCounter.server_uuid, serverCounter.counter - 1)

    def getAssignInformation(self, serverGroup: 'models.ServerGroup') -> typing.Dict[str, int]:
        """
        Get usage information for a server group

        Args:
            serverGroup: Server group to get current usage from

        Returns:
            Dict of current usage (user uuid, counter for assignations to that user)

        """
        res: typing.Dict[str, int] = {}
        for k, v in serverGroup.properties.items():
            if k.startswith(self.PROPERTY_BASE_NAME):
                kk = k[len(self.PROPERTY_BASE_NAME) :]  # Skip base name
                res[kk] = res.get(kk, 0) + v[1]
        return res

    def doMaintenance(self, serverGroup: 'models.ServerGroup') -> None:
        """Realizes maintenance on server group

        Maintenace operations include:
            * Clean up removed users from server counters

        Args:
            serverGroup: Server group to realize maintenance on
        """
        for k, v in serverGroup.properties.items():
            if k.startswith(self.PROPERTY_BASE_NAME):
                uuid = k[len(self.PROPERTY_BASE_NAME) :]
                try:
                    models.User.objects.get(uuid=uuid)
                except Exception:
                    # User does not exists, remove it from counters
                    del serverGroup.properties[k]

    def notifyPreconnect(
        self,
        server: 'models.Server',
        userService: 'models.UserService',
        info: types.connections.ConnectionDataType,
    ) -> None:
        """
        Notifies preconnect to server
        """
        requester.ServerApiRequester(server).notifyPreconnect(userService, info)

    def processEvent(self, server: 'models.Server', data: typing.Dict[str, typing.Any]) -> typing.Any:
        """
        Processes a notification FROM server
        That is, this is not invoked directly unless a REST request is received from
        a server.
        """
        return events.process(server, data)
