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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import pickle  # nosec # Pickle use is controled by app, never by non admin user input
import random
import typing
import collections.abc

from django.db import transaction
from django.utils.translation import gettext, gettext_lazy as _

from uds.core import exceptions, services, types
from uds.core.ui import gui
from uds.core.util import ensure, log, net
from uds.core.util.model import sql_stamp_seconds

from .deployment import IPMachineUserService
from .service_base import IPServiceBase
from .types import HostInfo

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class IPMachinesService(IPServiceBase):
    # Gui
    token = gui.TextField(
        order=1,
        label=typing.cast(str, _('Service Token')),
        length=64,
        tooltip=typing.cast(
            str,
            _(
                'Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'
            ),
        ),
        default='',
        required=False,
        readonly=False,
    )

    list_of_hosts = gui.EditableListField(
        label=typing.cast(str, _('List of hosts')),
        tooltip=typing.cast(str, _('List of hosts available for this service')),
        old_field_name='ipList',
    )

    port = gui.NumericField(
        length=5,
        label=typing.cast(str, _('Check Port')),
        default=0,
        order=2,
        tooltip=typing.cast(
            str, _('If non zero, only hosts responding to connection on that port will be served.')
        ),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    ignore_minutes_on_failure = gui.NumericField(
        length=6,
        label=typing.cast(str, _('Ignore minutes on failure')),
        default=0,
        order=2,
        tooltip=typing.cast(str, _('If a host fails to check, skip it for this time (in minutes).')),
        min_value=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='skipTimeOnFailure',
    )

    max_session_hours = gui.NumericField(
        length=3,
        label=typing.cast(str, _('Max session duration')),
        default=0,
        order=3,
        tooltip=typing.cast(
            str,
            _(
                'Max session duration before UDS releases a presumed locked machine (hours). 0 signifies "never".'
            ),
        ),
        min_value=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='maxSessionForMachine',
    )
    lock_on_external_access = gui.CheckBoxField(
        label=typing.cast(str, _('Lock machine by external access')),
        tooltip=typing.cast(str, _('If checked, UDS will lock the machine if it is accesed from outside UDS.')),
        default=False,
        order=4,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='lockByExternalAccess',
    )
    randomize_host = gui.CheckBoxField(
        label=typing.cast(str, _('Use random host')),
        tooltip=typing.cast(
            str, _('When enabled, UDS selects a random, rather than sequential, host from the list.')
        ),
        default=False,
        order=5,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='useRandomIp',
    )

    # Description of service
    type_name = typing.cast(str, _('Static Multiple IP'))
    type_type = 'IPMachinesService'
    type_description = typing.cast(str, _('This service provides access to POWERED-ON Machines by IP'))
    icon_file = 'machines.png'

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    must_assign_manually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    user_service_type = IPMachineUserService

    services_type_provided = types.services.ServiceType.VDI

    _cached_hosts: typing.Optional[typing.List['HostInfo']] = None

    def init_gui(self) -> None:
        # list_of_hosts is not stored on normar serializer, but on hosts
        self.list_of_hosts.value = [i.as_identifier() for i in self.hosts]

    def initialize(self, values: 'types.core.ValuesType') -> None:
        hosts_list = self.list_of_hosts.as_list()
        self.list_of_hosts.value = []  # Clear list of hosts, as it is now stored on hosts

        if values is None:
            return

        for v in hosts_list:
            if not net.is_valid_host(v.split(';')[0]):  # Get only IP/hostname
                raise exceptions.ui.ValidationError(
                    gettext('Invalid value detected on servers list: "{}"').format(v)
                )

        current_hosts = IPMachinesService.compose_hosts_info(hosts_list, add_order=True)

        # Remove repeated hosts from list, we cannot have two hosts with same IP
        current_hosts = sorted(set(current_hosts), key=lambda x: x.host)  # sort to ensure order is the correct :)
        dissapeared = set(i.host for i in self.hosts) - set(i.host for i in current_hosts)

        with transaction.atomic():
            for removable in dissapeared:
                self.storage.remove(removable)  # Clean up stored data for dissapeared hosts

        self.hosts = current_hosts

    @property
    def hosts(self) -> typing.List['HostInfo']:
        if self._cached_hosts is None:
            d = self.storage.read_from_db('ips')
            hosts_list = pickle.loads(d) if d and isinstance(d, bytes) else []  # nosec: pickle is safe here
            self._cached_hosts = IPMachinesService.compose_hosts_info(hosts_list)
        return self._cached_hosts

    @hosts.setter
    def hosts(self, hosts: typing.List['HostInfo']) -> None:
        self._cached_hosts = hosts
        self.storage.save_to_db('ips', pickle.dumps([i.as_str() for i in self.hosts]))

    @staticmethod
    def compose_hosts_info(hosts_list: list[str], add_order: bool = False) -> typing.List[HostInfo]:
        return [
            HostInfo.from_str(hostdata, '' if not add_order else str(counter))
            for counter, hostdata in enumerate(hosts_list)
            if hostdata.strip()
        ]

    def get_token(self) -> typing.Optional[str]:
        return self.token.as_str() or None

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)  # New format, use parent unmarshal

        values: list[bytes] = data.split(b'\0')
        # Ensure list of ips is at latest "old" format
        d = self.storage.read_from_db('ips')
        if isinstance(d, str):  # "legacy" saved elements
            _ips = pickle.loads(d.encode('utf8'))  # nosec: pickle is safe here
            self.storage.save_to_db('ips', pickle.dumps(_ips))

        self._cached_hosts = None  # Invalidate cache

        if values[0] != b'v1':
            self.token.value = values[1].decode()
            if values[0] in (b'v3', b'v4', b'v5', b'v6', b'v7'):
                self.port.value = int(values[2].decode())
            if values[0] in (b'v4', b'v5', b'v6', b'v7'):
                self.ignore_minutes_on_failure.value = int(values[3].decode())
            if values[0] in (b'v5', b'v6', b'v7'):
                self.max_session_hours.value = int(values[4].decode())
            if values[0] in (b'v6', b'v7'):
                self.lock_on_external_access.value = gui.as_bool(values[5].decode())
            if values[0] in (b'v7',):
                self.randomize_host.value = gui.as_bool(values[6].decode())

        # Sets maximum services for this, and loads "hosts" into cache
        self.userservices_limit = len(self.hosts)

        self.mark_for_upgrade()  # Flag for upgrade as soon as possible

    def is_usable(self, locked: typing.Optional[typing.Union[str, int]], now: int) -> int:
        # If _maxSessionForMachine is 0, it can be used only if not locked
        # (that is locked is None)
        locked = locked or 0
        if isinstance(locked, str) and not '.' in locked:  # Convert to int and treat it as a "locked" element
            locked = int(locked)

        if self.max_session_hours.as_int() <= 0:
            return not bool(locked)  # If locked is None, it can be used

        if not isinstance(locked, int):  # May have "old" data, that was the IP repeated
            return False

        if not locked or locked < now - self.max_session_hours.as_int() * 3600:
            return True

        return False

    def get_unassigned_host(self) -> typing.Optional['HostInfo']:
        # Search first unassigned machine
        try:
            now = sql_stamp_seconds()

            # Reorder ips, so we do not always get the same one if requested
            all_hosts = self.hosts
            if self.randomize_host:
                random.shuffle(all_hosts)

            for host in all_hosts:
                locked = self.storage.get_unpickle(host.host)
                # If it is not locked
                if self.is_usable(locked, now):
                    # If the check failed not so long ago, skip it...
                    if (
                        self.port.as_int() > 0
                        and self.ignore_minutes_on_failure.as_int() > 0
                        and self.cache.get(f'port{host.host}')
                    ):
                        continue
                    # Store/update lock time
                    self.storage.put_pickle(host.host, now)

                    # Is WOL enabled?
                    is_wakeonland_enabled = bool(self.provider().wake_on_lan_endpoint(host))
                    # Now, check if it is available on port, if required...
                    if (
                        self.port.as_int() > 0 and not is_wakeonland_enabled
                    ):  # If configured WOL, check is a nonsense
                        if net.test_connectivity(host.host, self.port.as_int(), timeout=0.5) is False:
                            # Log into logs of provider, so it can be "shown" on services logs
                            self.provider().do_log(
                                log.LogLevel.WARNING,
                                f'Host {host.host} not accesible on port {self.port.as_int()}',
                            )
                            logger.warning(
                                'Static Machine check on %s:%s failed. Will be ignored for %s minutes.',
                                host.host,
                                self.port.as_int(),
                                self.ignore_minutes_on_failure.as_int(),
                            )
                            self.storage.remove(host.host)  # Return Machine to pool
                            if self.ignore_minutes_on_failure.as_int() > 0:
                                self.cache.put(
                                    f'port{host.host}',
                                    '1',
                                    validity=self.ignore_minutes_on_failure.as_int() * 60,
                                )
                            continue
                    return host
            return None
        except Exception:
            logger.exception("Exception at getUnassignedMachine")
            return None

    def unassign_host(self, host: 'HostInfo') -> None:
        try:
            self.storage.remove(host.host)
        except Exception:
            logger.exception("Exception at getUnassignedMachine")

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        return [
            gui.choice_item(f'{host.host}|{host.mac}', host.host)
            for host in self.hosts
            if self.storage.read_from_db(host.host) is None
        ]

    def assign_from_assignables(
        self,
        assignable_id: str,
        user: 'models.User',
        userDeployment: 'services.UserService',
    ) -> str:
        userservice_instance: IPMachineUserService = typing.cast(IPMachineUserService, userDeployment)
        host = HostInfo.from_str(assignable_id)

        now = sql_stamp_seconds()
        locked = self.storage.get_unpickle(host.host)
        if self.is_usable(locked, now):
            self.storage.put_pickle(host.host, now)
            return userservice_instance.assign(host.as_identifier())

        return userservice_instance.error('IP already assigned')

    def process_login(self, id: str, remote_login: bool) -> None:
        '''
        Process login for a machine not assigned to any user.
        '''
        logger.debug('Processing login for %s: %s', self, id)

        # Locate the IP on the storage
        host = HostInfo.from_str(id)
        now = sql_stamp_seconds()
        locked: typing.Union[None, str, int] = self.storage.get_unpickle(host.host)
        if self.is_usable(locked, now):
            self.storage.put_pickle(host.host, str(now))  # Lock it

    def process_logout(self, id: str, remote_login: bool) -> None:
        '''
        Process logout for a machine not assigned to any user.
        '''
        logger.debug('Processing logout for %s: %s', self, id)
        # Locate the IP on the storage
        host = HostInfo.from_str(id)
        locked: typing.Union[None, str, int] = self.storage.get_unpickle(host.host)
        # If locked is str, has been locked by processLogin so we can unlock it
        if isinstance(locked, str):
            self.unassign_host(host)
        # If not proccesed by login, we cannot release it

    def notify_initialization(self, id: str) -> None:
        '''
        Notify that a machine has been initialized.
        Normally, this means that
        '''
        logger.debug('Notify initialization for %s: %s', self, id)
        self.unassign_host(HostInfo.from_str(id))

    def get_valid_id(self, ids: collections.abc.Iterable[str]) -> typing.Optional[str]:
        # If locking not allowed, return None
        if self.lock_on_external_access.as_bool() is False:
            return None
        # Look for the first valid id on our list
        for host in self.hosts:
            # If is managed by us
            if host.host in ids or host.mac in ids:
                return host.as_identifier()
        return None
