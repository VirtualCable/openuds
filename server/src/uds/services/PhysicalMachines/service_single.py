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
import collections.abc

from django.utils.translation import gettext_lazy as _, gettext

from uds.core.ui import gui
from uds.core.util import net
from uds.core import exceptions, types

from .deployment import IPMachineUserService
from .service_base import IPServiceBase
from .types import HostInfo

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class IPSingleMachineService(IPServiceBase):
    # Gui
    host = gui.TextField(
        length=64,
        label=_('Machine IP'),
        order=1,
        tooltip=_('Machine IP'),
        required=True,
        old_field_name='ip'
    )

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


    def initialize(self, values: 'Module.ValuesType') -> None:
        if values is None:
            return
        
        if ';' in self.host.as_str():
            ip, mac = self.host.as_str().split(';')

        if not net.is_valid_host(self.host.value):
            raise exceptions.ui.ValidationError(
                gettext('Invalid server used: "{}"'.format(self.host.value))
            )

    def get_unassigned_host(self) -> typing.Optional['HostInfo']:
        host: typing.Optional[HostInfo] = None
        try:
            counter = self.storage.get_unpickle('counter')
            counter = counter + 1 if counter is not None else 1
            self.storage.put_pickle('counter', counter)
            host = HostInfo(self.host.value, order=str(counter))
        except Exception:
            host = None
            logger.exception("Exception at get_unassigned_host")

        return host

    def unassign_host(self, host: 'HostInfo') -> None:
        pass
