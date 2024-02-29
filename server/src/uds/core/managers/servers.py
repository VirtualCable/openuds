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

if typing.TYPE_CHECKING:
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('traceLog')
operationsLogger = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    STORAGE_NAME: typing.Final[str] = 'uds.servers'
    MAX_COUNTERS_AGE: typing.Final[datetime.timedelta] = datetime.timedelta(days=3)
    BASE_PROPERTY_NAME: typing.Final[str] = 'sm_usr_'

    # Singleton, can initialize here
    last_counters_clean: datetime.datetime = datetime.datetime.now()

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    def counter_storage(self) -> 'StorageAccess':
        # If counters are too old, restart them
        if datetime.datetime.now() - self.last_counters_clean > self.MAX_COUNTERS_AGE:
            self.clear_unmanaged_usage()
        return Storage(self.STORAGE_NAME).as_dict(atomic=True, group='counters')

    def property_name(self, user: typing.Optional[typing.Union[str, 'models.User']]) -> str:
        """Returns the property name for a user"""
        if isinstance(user, str):
            return ServerManager.BASE_PROPERTY_NAME + user
        return ServerManager.BASE_PROPERTY_NAME + (str(user.uuid) if user else '_')

    def clear_unmanaged_usage(self) -> None:
        with self.counter_storage() as counters:
            counters.clear()
        self.last_counters_clean = datetime.datetime.now()

    def get_unmanaged_usage(self, uuid: str) -> int:
        uuid = 'c' + uuid
        with self.counter_storage() as counters:
            return counters.get(uuid, 0)

    def decrement_unmanaged_usage(self, uuid: str, force_reset: bool = False) -> None:
        uuid = 'c' + uuid
        with self.counter_storage() as counters:
            if uuid in counters:
                counters[uuid] -= 1
                if counters[uuid] <= 0 or force_reset:
                    del counters[uuid]

    def increment_unmanaged_usage(self, uuid: str, only_if_exists: bool = False) -> None:
        uuid = 'c' + uuid
        with self.counter_storage() as counters:
            if not only_if_exists or uuid in counters:
                counters[uuid] = counters.get(uuid, 0) + 1

    def get_server_stats(
        self, serversFltr: 'QuerySet[models.Server]'
    ) -> list[tuple[typing.Optional['types.servers.ServerStats'], 'models.Server']]:
        """
        Returns a list of stats for a list of servers
        """
        # Paralelize stats retrieval
        retrieved_stats: list[tuple[typing.Optional['types.servers.ServerStats'], 'models.Server']] = []

        def _retrieve_stats(server: 'models.Server') -> None:
            try:
                retrieved_stats.append(
                    (requester.ServerApiRequester(server).get_stats(), server)
                )  # Store stats for later use
            except Exception:
                retrieved_stats.append((None, server))

        # Retrieve, in parallel, stats for all servers (not restrained)
        with ThreadPoolExecutor(max_workers=10) as executor:
            for server in serversFltr.select_for_update():
                if server.is_restrained():
                    continue  # Skip restrained servers
                executor.submit(_retrieve_stats, server)

        return retrieved_stats

    def _find_best_server(
        self,
        userservice: 'models.UserService',
        server_group: 'models.ServerGroup',
        now: datetime.datetime,
        min_memory_mb: int = 0,
        excluded_servers_uuids: typing.Optional[typing.Set[str]] = None,
    ) -> tuple['models.Server', 'types.servers.ServerStats']:
        """
        Finds the best server for a service
        """
        best: typing.Optional[tuple['models.Server', 'types.servers.ServerStats']] = None
        unmanaged_list: list['models.Server'] = []
        fltrs = server_group.servers.filter(maintenance_mode=False)
        fltrs = fltrs.filter(Q(locked_until=None) | Q(locked_until__lte=now))  # Only unlocked servers
        if excluded_servers_uuids:
            fltrs = fltrs.exclude(uuid__in=excluded_servers_uuids)

        serversStats = self.get_server_stats(fltrs)

        # Now, cachedStats has a list of tuples (stats, server), use it to find the best server
        for stats, server in serversStats:
            if stats is None:
                unmanaged_list.append(server)
                continue
            if min_memory_mb and stats.memused // (1024 * 1024) < min_memory_mb:  # Stats has minMemory in bytes
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
                [(s, self.get_unmanaged_usage(s.uuid)) for s in unmanaged_list], key=lambda x: x[1]
            )[0]
            # Update counter
            self.increment_unmanaged_usage(best_with_counter[0].uuid)
            best = (
                best_with_counter[0],
                types.servers.ServerStats.empty(),
            )

        # If best was locked, notify it (will be notified again on assign)
        if best[0].locked_until is not None:
            requester.ServerApiRequester(best[0]).notify_release(userservice)

        return best

    def assign(
        self,
        userservice: 'models.UserService',
        server_group: 'models.ServerGroup',
        service_type: types.services.ServiceType = types.services.ServiceType.VDI,
        min_memory_mb: int = 0,  # Does not apply to unmanged servers
        lock_interval: typing.Optional[datetime.timedelta] = None,
        server: typing.Optional['models.Server'] = None,  # If not note
        excluded_servers_uuids: typing.Optional[typing.Set[str]] = None,
    ) -> typing.Optional[types.servers.ServerCounter]:
        """
        Select a server for an userservice to be assigned to

        Args:
            userservice: User service to assign server to (in fact, user of userservice) and to notify
            server_group: Server group to select server from
            service_type: Type of service to assign
            min_memory_mb: Minimum memory required for server in MB, does not apply to unmanaged servers
            lock_interval: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from serverGroup. (Used on manual assign)
            excluded_servers_uuids: If not None, exclude this servers from selection. Used in case we check the availability of a server
                                 with some external method and we want to exclude it from selection because it has already failed.

        Returns:
            uuid of server assigned
        """
        if not userservice.user:
            raise exceptions.UDSException(_('No user assigned to service'))

        # Look for existing user asignation through properties
        prop_name = self.property_name(userservice.user)
        now = model_utils.sql_datetime()

        excluded_servers_uuids = excluded_servers_uuids or set()

        with server_group.properties as props:
            info: typing.Optional[types.servers.ServerCounter] = types.servers.ServerCounter.from_iterable(
                props.get(prop_name)
            )
            # If server is forced, and server is part of the group, use it
            if server:
                if (
                    server.groups.filter(uuid=server_group.uuid).exclude(uuid__in=excluded_servers_uuids).count()  
                    == 0
                ):
                    raise exceptions.UDSException(_('Server is not part of the group'))
                elif server.maintenance_mode:
                    raise exceptions.UDSException(_('Server is in maintenance mode'))
                elif server.is_restrained():
                    raise exceptions.UDSException(_('Server is restrained'))

                # if server.uuid is stored uuid, increase counter (and counters if exits), else store it
                if info and info.server_uuid == server.uuid:
                    info = types.servers.ServerCounter(server.uuid, info.counter + 1)
                else:
                    props[prop_name] = (server.uuid, 0)
                    info = types.servers.ServerCounter(server.uuid, 0)

                self.increment_unmanaged_usage(server.uuid, only_if_exists=True)
            else:
                if info and info.server_uuid:
                    # If server does not exists, or it is in maintenance, or it is in exclude list or it is restrained,
                    # remove it from saved and use look for another one
                    svr = models.Server.objects.filter(uuid=info.server_uuid).first()
                    if not svr or (
                        svr.maintenance_mode or svr.uuid in excluded_servers_uuids or svr.is_restrained()
                    ):
                        info = None
                        del props[prop_name]
                    else:
                        # Increase "local" counters for RR if needed
                        self.increment_unmanaged_usage(info.server_uuid, only_if_exists=True)
                # If no existing assignation, check for a new one
                if info is None:
                    try:
                        with transaction.atomic():
                            best = self._find_best_server(
                                userservice=userservice,
                                server_group=server_group,
                                now=now,
                                min_memory_mb=min_memory_mb,
                                excluded_servers_uuids=excluded_servers_uuids,
                            )

                            info = types.servers.ServerCounter(best[0].uuid, 0)
                            best[0].locked_until = now + lock_interval if lock_interval else None
                            best[0].save(update_fields=['locked_until'])
                    except exceptions.UDSException:  # No more servers
                        return None
                elif lock_interval:  # If lockTime is set, update it
                    models.Server.objects.filter(uuid=info.server_uuid).update(locked_until=now + lock_interval)

            # Notify to server
            # Update counter
            info = types.servers.ServerCounter(info.server_uuid, info.counter + 1)
            props[prop_name] = info
            bestServer = models.Server.objects.get(uuid=info.server_uuid)

            # Ensure next assignation will have updated stats
            # This is a simple simulation on cached stats, will be updated on next stats retrieval
            # (currently, cache time is 1 minute)
            bestServer.interpolate_new_assignation()

        # Notify assgination in every case, even if reassignation to same server is made
        # This lets the server to keep track, if needed, of multi-assignations
        self.notify_assign(bestServer, userservice, service_type, info.counter)
        return info

    def release(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
        unlock: bool = False,
        userUuid: typing.Optional[str] = None,
    ) -> types.servers.ServerCounter:
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
            return types.servers.ServerCounter.null()  # No user is assigned to this service, nothing to do

        prop_name = self.property_name(userService.user)
        with serverGroup.properties as props:
            with transaction.atomic():
                resetCounter = False
                # ServerCounterType

                serverCounter: typing.Optional[
                    types.servers.ServerCounter
                ] = types.servers.ServerCounter.from_iterable(props.get(prop_name))
                # If no cached value, get server assignation
                if serverCounter is None:
                    return types.servers.ServerCounter.null()
                # Ensure counter is at least 1
                serverCounter = types.servers.ServerCounter(
                    serverCounter.server_uuid, max(1, serverCounter.counter)
                )
                if serverCounter.counter == 1 or unlock:
                    # Last one, remove it
                    del props[prop_name]
                else:  # Not last one, just decrement counter
                    props[prop_name] = (serverCounter.server_uuid, serverCounter.counter - 1)

            server = models.Server.objects.get(uuid=serverCounter.server_uuid)

            if unlock or serverCounter.counter == 1:
                server.locked_until = None  # Ensure server is unlocked if no more users are assigned to it
                server.save(update_fields=['locked_until'])

                # Enure server counter is cleaned also, because server is considered "fully released"
                resetCounter = True

            # If unmanaged, decrease usage
            if server.type == types.servers.ServerType.UNMANAGED:
                self.decrement_unmanaged_usage(server.uuid, force_reset=resetCounter)

            # Ensure next assignation will have updated stats
            # This is a simple simulation on cached stats, will be updated on next stats retrieval
            # (currently, cache time is 1 minute)
            server.interpolate_new_release()

            self.notify_release(server, userService)

        return types.servers.ServerCounter(serverCounter.server_uuid, serverCounter.counter - 1)

    def notify_preconnect(
        self,
        serverGroup: 'models.ServerGroup',
        userService: 'models.UserService',
        info: types.connections.ConnectionData,
        server: typing.Optional[
            'models.Server'
        ] = None,  # Forced server instead of selecting one from serverGroup
    ) -> None:
        """
        Notifies preconnect to server
        """
        if not server:
            server = self.server_assignation_for(userService, serverGroup)

        if server:
            requester.ServerApiRequester(server).notify_preconnect(userService, info)

    def notify_assign(
        self,
        server: 'models.Server',
        userService: 'models.UserService',
        serviceType: types.services.ServiceType,
        counter: int,
    ) -> None:
        """
        Notifies assign to server
        """
        requester.ServerApiRequester(server).notify_assign(userService, serviceType, counter)

    def notify_release(
        self,
        server: 'models.Server',
        userService: 'models.UserService',
    ) -> None:
        """
        Notifies release to server
        """
        requester.ServerApiRequester(server).notify_release(userService)

    def assignation_info(self, serverGroup: 'models.ServerGroup') -> dict[str, int]:
        """
        Get usage information for a server group

        Args:
            serverGroup: Server group to get current usage from

        Returns:
            Dict of current usage (user uuid, counter for assignations to that user)

        """
        res: dict[str, int] = {}
        for k, v in serverGroup.properties.items():
            if k.startswith(self.BASE_PROPERTY_NAME):
                kk = k[len(self.BASE_PROPERTY_NAME) :]  # Skip base name
                res[kk] = res.get(kk, 0) + v[1]
        return res

    def server_assignation_for(
        self,
        userService: 'models.UserService',
        serverGroup: 'models.ServerGroup',
    ) -> typing.Optional['models.Server']:
        """
        Returns the server assigned to an user service

        Args:
            userService: User service to get server from
            serverGroup: Server group to get server from

        Returns:
            Server assigned to user service, or None if no server is assigned
        """
        if not userService.user:
            raise exceptions.UDSException(_('No user assigned to service'))

        prop_name = self.property_name(userService.user)
        with serverGroup.properties as props:
            info: typing.Optional[types.servers.ServerCounter] = types.servers.ServerCounter.from_iterable(
                props.get(prop_name)
            )
            if info is None:
                return None
            return models.Server.objects.get(uuid=info.server_uuid)

    def sorted_server_list(
        self,
        serverGroup: 'models.ServerGroup',
        excludeServersUUids: typing.Optional[typing.Set[str]] = None,
    ) -> list['models.Server']:
        """
        Returns a list of servers sorted by usage

        Args:
            serverGroup: Server group to get servers from

        Returns:
            List of servers sorted by usage
        """
        with transaction.atomic():
            now = model_utils.sql_datetime()
            fltrs = serverGroup.servers.filter(maintenance_mode=False)
            fltrs = fltrs.filter(Q(locked_until=None) | Q(locked_until__lte=now))  # Only unlocked servers
            if excludeServersUUids:
                fltrs = fltrs.exclude(uuid__in=excludeServersUUids)

            # Get the stats for all servers, but in parallel
            serverStats = self.get_server_stats(fltrs)
        # Sort by weight, lower first (lower is better)
        return [s[1] for s in sorted(serverStats, key=lambda x: x[0].weight() if x[0] else 999999999)]

    def perform_maintenance(self, serverGroup: 'models.ServerGroup') -> None:
        """Realizes maintenance on server group

        Maintenace operations include:
            * Clean up removed users from server counters

        Args:
            serverGroup: Server group to realize maintenance on
        """
        for k, _ in serverGroup.properties.items():
            if k.startswith(self.BASE_PROPERTY_NAME):
                uuid = k[len(self.BASE_PROPERTY_NAME) :]
                try:
                    models.User.objects.get(uuid=uuid)
                except Exception:
                    # User does not exists, remove it from counters
                    del serverGroup.properties[k]

    def process_event(self, server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
        """
        Processes a notification FROM server
        That is, this is not invoked directly unless a REST request is received from
        a server.
        """
        return events.process(server, data)
