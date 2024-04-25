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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_lazy as _, gettext

from uds.core.ui import gui
from uds.core.util import net
from uds.core import exceptions, types, services
from uds.core.util import security

from .deployment import IPMachineUserService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import provider

logger = logging.getLogger(__name__)


class IPSingleMachineService(services.Service):
    # Description of service
    type_name = _('Static Single IP')
    type_type = 'IPSingleMachineService'
    type_description = _('This service provides access to POWERED-ON Machine by IP')
    icon_file = 'machine.png'

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_osmanager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    must_assign_manually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    user_service_type = IPMachineUserService

    services_type_provided = types.services.ServiceType.VDI
    
    # Gui
    host = gui.TextField(
        length=64,
        label=_('Host IP/FQDN'),
        order=1,
        tooltip=_('IP or FQDN of the server to connect to. Can include MAC address separated by ";" after the IP/Hostname'),
        required=True,
        old_field_name='ip',
    )


    def get_host_mac(self) -> typing.Tuple[str, str]:
        if ';' in self.host.as_str():
            return typing.cast(tuple[str, str], tuple(self.host.as_str().split(';', 2)[:2]))
        return self.host.as_str(), ''

    def initialize(self, values: 'types.core.ValuesType') -> None:
        if values is None:
            return

        host, mac = self.get_host_mac()

        if not net.is_valid_host(host):
            raise exceptions.ui.ValidationError(gettext('Invalid server used: "{}"'.format(self.host.value)))

        if mac and not net.is_valid_mac(mac):
            raise exceptions.ui.ValidationError(gettext('Invalid MAC address used: "{}"'.format(mac)))

    def get_unassigned_host(self) -> typing.Optional[tuple[str, str]]:
        return self.get_host_mac()

    def provider(self) -> 'provider.PhysicalMachinesProvider':
        return typing.cast('provider.PhysicalMachinesProvider', super().provider())

    def wakeup(self, verify_ssl: bool = False) -> None:
        host, mac = self.get_host_mac()
        if mac:
            wake_on_land_endpoint = self.provider().wake_on_lan_endpoint(host, mac)
            if wake_on_land_endpoint:
                logger.info('Launching WOL: %s', wake_on_land_endpoint)
                try:
                    security.secure_requests_session(verify=verify_ssl).get(wake_on_land_endpoint)
                    # logger.debug('Result: %s', result)
                except Exception as e:
                    logger.error('Error on WOL: %s', e)

    def get_counter_and_inc(self) -> int:
        with self.storage.as_dict() as storage:
            counter = storage.get('counter', 0)
            storage['counter'] = counter + 1
            return counter

    # Phisical machines does not have "real" providers, so
    # always is available
    def is_avaliable(self) -> bool:
        return True
