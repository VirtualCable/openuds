#
# Copyright (c) 2023-2024 Virtual Cable S.L.U.
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
import contextlib
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
from uds.core.util.storage import StorageAsDict, Storage

from .servers_api import events, requester

if typing.TYPE_CHECKING:
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)
logger_trace = logging.getLogger('traceLog')
logger_operations = logging.getLogger('operationsLog')


class ServerManager(metaclass=singleton.Singleton):
    STORAGE_NAME: typing.Final[str] = 'uds.servers'
    MAX_COUNTERS_AGE: typing.Final[datetime.timedelta] = datetime.timedelta(days=3)
    BASE_PROPERTY_NAME: typing.Final[str] = 'sm_usr_'

    # Singleton, can initialize here
    last_counters_clean: datetime.datetime = datetime.datetime.now()  # This is local to server, so it's ok

    @staticmethod
    def manager() -> 'ServerManager':
        return ServerManager()  # Singleton pattern will return always the same instance

    @contextlib.contextmanager
    def counter_storage(self) -> typing.Iterator[StorageAsDict]:
        with Storage(self.STORAGE_NAME).as_dict(atomic=True, group='counters') as storage:
            # If counters are too old, restart them
            if datetime.datetime.now() - self.last_counters_clean > self.MAX_COUNTERS_AGE:
                self.last_counters_clean = datetime.datetime.now()
                storage.clear()
            yield storage

    def property_name(self, user: typing.Optional[typing.Union[str, 'models.User']]) -> str:
        """Returns the property name for a user"""
        if isinstance(user, str):
            return ServerManager.BASE_PROPERTY_NAME + user
        return ServerManager.BASE_PROPERTY_NAME + (str(user.uuid) if user else '_')

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
        self, servers_filter: 'QuerySet[models.Server]'
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
        # Not using a transaction here, as we are only reading data
        with ThreadPoolExecutor(max_workers=10) as executor:
            for server in servers_filter.all():
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
        *,
        weight_threshold: int = 0,  # If not 0, server with weight below and nearer to this value will be selected
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

        stats_and_servers = self.get_server_stats(fltrs)

        weight_threshold_f = weight_threshold / 100

        def _real_weight(stats: 'types.servers.ServerStats') -> float:
            stats_weight = stats.load()

            if weight_threshold == 0:
                return stats_weight

            # Values under threshold are better, weight is in between 0 and 1, lower is better
            # To values over threshold, we will add 1, so they are always worse than any value under threshold
            # No matter if over threshold is overcalculed, it will be always worse than any value under threshold
            # and all values over threshold will be affected in the same way
            weight = (
                weight_threshold_f - stats_weight if stats_weight < weight_threshold_f else 1 + stats_weight
            )

            # logger.info('Stats: %s', stats)
            # logger.info(
            #     'Stats weight: %s, threshold: %s, calculated: %s', stats_weight, weight_threshold, weight
            # )

            return weight

        # Now, cachedStats has a list of tuples (stats, server), use it to find the best server
        for stats, server in stats_and_servers:
            if stats is None:
                unmanaged_list.append(server)
                continue
            if min_memory_mb and stats.memused // (1024 * 1024) < min_memory_mb:  # Stats has minMemory in bytes
                continue

            if best is None:
                best = (server, stats)

            if _real_weight(stats) < _real_weight(best[1]):
                best = (server, stats)

            # stats.weight() < best[1].weight()

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
                types.servers.ServerStats.null(),
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
        *,
        weight_threshold: int = 0,
    ) -> typing.Optional[types.servers.ServerCounter]:
        """
        Select a server for an userservice to be assigned to

        Args:
            userservice: User service to assign server to (in fact, user of userservice) and to notify
            server_group: Server group to select server from
            service_type: Type of service to assign
            min_memory_mb: Minimum memory required for server in MB, does not apply to unmanaged servers
            lock_interval: If not None, lock server for this time
            server: If not None, use this server instead of selecting one from server_group. (Used on manual assign)
            excluded_servers_uuids: If not None, exclude this servers from selection. Used in case we check the availability of a server
                                 with some external method and we want to exclude it from selection because it has already failed.
            weight_threshold: If not 0, basically will prefer values below an near this value

            Note:
                weight_threshold is used to select a server with a weight as near as possible, without going over, to this value.
                If none is found, the server with the lowest weight will be selected.
                If 0, no weight threshold is applied.
                The calculation is done as follows (with weight_threshold > 0 ofc):
                   * if weight is below threshold, (threshold - weight) is returned (so nearer to threshold, better)
                   * if weight is over threshold, 1 + weight is returned (so, all values over threshold are worse than any value under threshold)
                   that is:
                    real_weight = weight_threshold - weight if weight < weight_threshold else 1 + weight

                The idea behind this is to be able to select a server not fully empty, but also not fully loaded, so it can be used
                to leave servers empty as soon as possible, but also to not overload servers that are near to be full.

        Returns:
            uuid of server assigned
        """
        if not userservice.user:
            raise exceptions.UDSException(_('No user assigned to service'))

        # Look for existing user asignation through properties
        prop_name = self.property_name(userservice.user)
        now = model_utils.sql_now()

        excluded_servers_uuids = excluded_servers_uuids or set()

        with server_group.properties as props:
            info: typing.Optional[types.servers.ServerCounter] = types.servers.ServerCounter.from_iterable(
                props.get(prop_name)
            )
            # If server is forced, and server is part of the group, use it
            if server:
                if (
                    server.groups.filter(uuid=server_group.uuid)
                    .exclude(uuid__in=excluded_servers_uuids)
                    .count()
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
                                weight_threshold=weight_threshold,
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
            best_server = models.Server.objects.get(uuid=info.server_uuid)

            # Ensure next assignation will have updated stats
            # This is a simple simulation on cached stats, will be updated on next stats retrieval
            # (currently, cache time is 1 minute)
            best_server.interpolate_new_assignation()

        # Notify assgination in every case, even if reassignation to same server is made
        # This lets the server to keep track, if needed, of multi-assignations
        self.notify_assign(best_server, userservice, service_type, info.counter)
        return info

    def release(
        self,
        userservice: 'models.UserService',
        server_group: 'models.ServerGroup',
        unlock: bool = False,
    ) -> types.servers.ServerCounter:
        """
        Unassigns a server from an user

        Args:
            userservice: User service to unassign server from
            server_group: Server group to unassign server from
            unlock: If True, unlock server, even if it has more users assigned to it
            user_uuid: If not None, use this uuid instead of userservice.user.uuid
        """
        user_uuid = userservice.user.uuid if userservice.user else None

        if user_uuid is None:
            return types.servers.ServerCounter.null()  # No user is assigned to this service, nothing to do

        prop_name = self.property_name(userservice.user)
        with server_group.properties as props:
            with transaction.atomic():
                reset_counter = False
                # ServerCounterType

                server_counter: typing.Optional[types.servers.ServerCounter] = (
                    types.servers.ServerCounter.from_iterable(props.get(prop_name))
                )
                # If no cached value, get server assignation
                if server_counter is None:
                    return types.servers.ServerCounter.null()
                # Ensure counter is at least 1
                server_counter = types.servers.ServerCounter(
                    server_counter.server_uuid, max(1, server_counter.counter)
                )
                if server_counter.counter == 1 or unlock:
                    # Last one, remove it
                    del props[prop_name]
                else:  # Not last one, just decrement counter
                    props[prop_name] = (server_counter.server_uuid, server_counter.counter - 1)

            server = models.Server.objects.get(uuid=server_counter.server_uuid)

            if unlock or server_counter.counter == 1:
                server.locked_until = None  # Ensure server is unlocked if no more users are assigned to it
                server.save(update_fields=['locked_until'])

                # Enure server counter is cleaned also, because server is considered "fully released"
                reset_counter = True

            # If unmanaged, decrease usage
            if server.type == types.servers.ServerType.UNMANAGED:
                self.decrement_unmanaged_usage(server.uuid, force_reset=reset_counter)

            # Ensure next assignation will have updated stats
            # This is a simple simulation on cached stats, will be updated on next stats retrieval
            # (currently, cache time is 1 minute)
            server.interpolate_new_release()

            self.notify_release(server, userservice)

        return types.servers.ServerCounter(server_counter.server_uuid, server_counter.counter - 1)

    def notify_preconnect(
        self,
        server_group: 'models.ServerGroup',
        userservice: 'models.UserService',
        info: types.connections.ConnectionData,
        server: typing.Optional[
            'models.Server'
        ] = None,  # Forced server instead of selecting one from server_group
    ) -> None:
        """
        Notifies preconnect to server
        """
        if not server:
            server = self.server_assignation_for(userservice, server_group)

        if server:
            requester.ServerApiRequester(server).notify_preconnect(userservice, info)

    def notify_assign(
        self,
        server: 'models.Server',
        userservice: 'models.UserService',
        service_type: types.services.ServiceType,
        counter: int,
    ) -> None:
        """
        Notifies assign to server
        """
        requester.ServerApiRequester(server).notify_assign(userservice, service_type, counter)

    def notify_release(
        self,
        server: 'models.Server',
        userservice: 'models.UserService',
    ) -> None:
        """
        Notifies release to server
        """
        requester.ServerApiRequester(server).notify_release(userservice)

    def assignation_info(self, server_group: 'models.ServerGroup') -> dict[str, int]:
        """
        Get usage information for a server group

        Args:
            server_group: Server group to get current usage from

        Returns:
            Dict of current usage (user uuid, counter for assignations to that user)

        """
        res: dict[str, int] = {}
        for k, v in server_group.properties.items():
            if k.startswith(self.BASE_PROPERTY_NAME):
                kk = k[len(self.BASE_PROPERTY_NAME) :]  # Skip base name
                res[kk] = res.get(kk, 0) + v[1]
        return res

    def server_assignation_for(
        self,
        userservice: 'models.UserService',
        server_group: 'models.ServerGroup',
    ) -> typing.Optional['models.Server']:
        """
        Returns the server assigned to an user service

        Args:
            userservice: User service to get server from
            server_group: Server group to get server from

        Returns:
            Server assigned to user service, or None if no server is assigned
        """
        if not userservice.user:
            raise exceptions.UDSException(_('No user assigned to service'))

        prop_name = self.property_name(userservice.user)
        with server_group.properties as props:
            info: typing.Optional[types.servers.ServerCounter] = types.servers.ServerCounter.from_iterable(
                props.get(prop_name)
            )
            if info is None:
                return None
            return models.Server.objects.get(uuid=info.server_uuid)

    def sorted_server_list(
        self,
        server_group: 'models.ServerGroup',
        excluded_servers_uuids: typing.Optional[typing.Set[str]] = None,
    ) -> list['models.Server']:
        """
        Returns a list of servers sorted by usage

        Args:
            server_group: Server group to get servers from

        Returns:
            List of servers sorted by usage
        """
        now = model_utils.sql_now()
        fltrs = server_group.servers.filter(maintenance_mode=False)
        fltrs = fltrs.filter(Q(locked_until=None) | Q(locked_until__lte=now))  # Only unlocked servers
        if excluded_servers_uuids:
            fltrs = fltrs.exclude(uuid__in=excluded_servers_uuids)

        # Get the stats for all servers, but in parallel
        server_stats = self.get_server_stats(fltrs)
        # Sort by load, lower first (lower is better)
        return [s[1] for s in sorted(server_stats, key=lambda x: x[0].load() if x[0] else 999999999)]

    def perform_maintenance(self, server_group: 'models.ServerGroup') -> None:
        """Realizes maintenance on server group

        Maintenace operations include:
            * Clean up removed users from server counters

        Args:
            server_group: Server group to realize maintenance on
        """
        for k, _ in server_group.properties.items():
            if k.startswith(self.BASE_PROPERTY_NAME):
                uuid = k[len(self.BASE_PROPERTY_NAME) :]
                try:
                    models.User.objects.get(uuid=uuid)
                except Exception:
                    # User does not exists, remove it from counters
                    del server_group.properties[k]

    def process_event(self, server: 'models.Server', data: dict[str, typing.Any]) -> typing.Any:
        """
        Processes a notification FROM server
        That is, this is not invoked directly unless a REST request is received from
        a server.
        """
        return events.process(server, data)
