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
import datetime
import random
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy as _

from uds import models
from uds.core import exceptions, types, services
from uds.core.ui import gui
from uds.core.util import fields
from uds.core.util.model import sql_datetime
from uds.core.util import security
from uds.core import services

from .deployment_multi import IPMachinesUserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import provider

logger = logging.getLogger(__name__)


class IPMachinesService(services.Service):
    # Gui
    token = gui.TextField(
        order=1,
        label=_('Service Token'),
        length=64,
        tooltip=_(
            'Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'
        ),
        default='',
        required=False,
        readonly=False,
    )

    server_group = fields.server_group_field(
        [types.servers.ServerType.SERVER, types.servers.ServerType.UNMANAGED], types.servers.IP_SUBTYPE
    )

    port = gui.NumericField(
        length=5,
        label=_('Check Port'),
        default=0,
        order=2,
        tooltip=_('If non zero, only hosts responding to connection on that port will be served.'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    ignore_minutes_on_failure = gui.NumericField(
        length=6,
        label=_('Ignore minutes on failure'),
        default=0,
        order=2,
        tooltip=_('If a host fails to check, skip it for this time (in minutes).'),
        min_value=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='skipTimeOnFailure',
    )

    max_session_hours = gui.NumericField(
        length=3,
        label=_('Max session duration'),
        default=0,
        order=3,
        tooltip=_(
            'Max session duration before UDS releases a presumed locked machine (hours). 0 signifies "never".'
        ),
        min_value=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='maxSessionForMachine',
    )
    lock_on_external_access = gui.CheckBoxField(
        label=_('Lock machine by external access'),
        tooltip=_('If checked, UDS will lock the machine if it is accessed from outside UDS.'),
        default=False,
        order=4,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='lockByExternalAccess',
    )
    randomize_host = gui.CheckBoxField(
        label=_('Use random host'),
        tooltip=_('When enabled, UDS selects a random, rather than sequential, host from the list.'),
        default=False,
        order=5,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='useRandomIp',
    )

    # Description of service
    type_name = _('Static Multiple IP')
    type_type = 'IPMachinesService'
    type_description = _('This service provides access to POWERED-ON Machines by IP')
    icon_file = 'machines.png'

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    must_assign_manually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    user_service_type = IPMachinesUserService

    services_type_provided = types.services.ServiceType.VDI

    def get_token(self) -> typing.Optional[str]:
        return self.token.as_str() or None

    def get_max_lock_time(self) -> datetime.timedelta:
        if self.max_session_hours.value == 0:
            return datetime.timedelta(days=365 * 32)  # 32 years (forever, or almost :) )
        return datetime.timedelta(hours=self.max_session_hours.value)

    def enumerate_assignables(self) -> collections.abc.Iterable[types.ui.ChoiceItem]:
        now = sql_datetime()
        return [
            gui.choice_item(f'{server.host}|{server.mac}', server.uuid)
            for server in fields.get_server_group_from_field(self.server_group).servers.all()
            if server.locked_until is None or server.locked_until < now
        ]

    def assign_from_assignables(
        self,
        assignable_id: str,
        user: 'models.User',
        userservice_instance: 'services.UserService',
    ) -> types.states.TaskState:
        server: 'models.Server' = models.Server.objects.get(uuid=assignable_id)
        ipmachine_instance: IPMachinesUserService = typing.cast(IPMachinesUserService, userservice_instance)
        if server.locked_until is None or server.locked_until < sql_datetime():
            # Lock the server for 10 year right now...
            server.locked_until = sql_datetime() + datetime.timedelta(days=365)

            return ipmachine_instance.assign(server.host)

        return ipmachine_instance._error('IP already assigned')
    
    def get_unassigned(self) -> str:
        '''
        Returns an unassigned machine
        '''
        list_of_servers = list(fields.get_server_group_from_field(self.server_group).servers.all())
        if self.randomize_host.as_bool() is True:
            random.shuffle(list_of_servers)  # Reorder the list randomly if required
            for server in list_of_servers:
                if server.locked_until is None or server.locked_until < sql_datetime():
                    return server.uuid
        raise exceptions.services.InsufficientResourcesException()
    
    def get_host_mac(self, server_uuid: str) -> typing.Tuple[str, str]:
        server = models.Server.objects.get(uuid=server_uuid)
        return server.host, server.mac

    def assign(self, server_uuid: str) -> None:
        try:
            server = models.Server.objects.get(uuid=server_uuid)
            server.lock(self.get_max_lock_time())
        except models.Server.DoesNotExist:
            pass

    def unassign(self, server_uuid: str) -> None:
        try:
            server = models.Server.objects.get(uuid=server_uuid)
            server.lock(None)
        except models.Server.DoesNotExist:
            pass

    def process_login(self, id: str, remote_login: bool) -> None:
        '''
        Process login for a machine not assigned to any user.
        '''
        logger.debug('Processing login for %s: %s', self, id)
        # Maybe, an user has logged in on an unassigned machine
        # if lockForExternalAccess is enabled, we must lock it
        if self.lock_on_external_access.as_bool() is True:
            self.assign(id)

    def process_logout(self, id: str, remote_login: bool) -> None:
        '''
        Process logout for a machine and release it.
        '''
        self.unassign(id)

    def notify_initialization(self, id: str) -> None:
        '''
        Notify that a machine has been initialized.
        Normally, this means that it's free
        '''
        logger.debug('Notify initialization for %s: %s', self, id)
        self.unassign(id)

    # Used by actor API. look parent documentation
    def get_valid_id(self, ids: collections.abc.Iterable[str]) -> typing.Optional[str]:
        # If locking not allowed, return None
        if self.lock_on_external_access.as_bool() is False:
            return None
        # Look for the first valid id on our list
        for server in fields.get_server_group_from_field(self.server_group).servers.all():
            # If is managed by us
            if (server.ip.strip() and server.ip in ids) or server.mac in ids:
                return server.uuid
        return None

    def provider(self) -> 'provider.PhysicalMachinesProvider':
        return typing.cast('provider.PhysicalMachinesProvider', super().provider())

    def wakeup(self, host: str, mac: str, verify_ssl: bool = False) -> None:
        if mac:
            wake_on_land_endpoint = self.provider().wake_on_lan_endpoint(host, mac)
            if wake_on_land_endpoint:
                logger.info('Launching WOL: %s', wake_on_land_endpoint)
                try:
                    security.secure_requests_session(verify=verify_ssl).get(wake_on_land_endpoint)
                    # logger.debug('Result: %s', result)
                except Exception as e:
                    logger.error('Error on WOL: %s', e)

    # Phisical machines does not have "real" providers, so
    # always is available
    def is_avaliable(self) -> bool:
        return True

