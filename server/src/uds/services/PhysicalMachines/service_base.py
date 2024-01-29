# -*- coding: utf-8 -*-

#
# Copyright (c) 2019-2021 Virtual Cable S.L.U.
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
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"u
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
import dataclasses
import logging
import stat
import typing
import collections.abc

from uds.core.util import security
from uds.core import services

from .types import HostInfo

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from . import provider


class IPServiceBase(services.Service):
    def parent(self) -> 'provider.PhysicalMachinesProvider':
        return typing.cast('provider.PhysicalMachinesProvider', super().parent())

    def get_unassigned_host(self) -> typing.Optional['HostInfo']:
        raise NotImplementedError('getUnassignedMachine')

    def unassign_host(self, host: 'HostInfo') -> None:
        raise NotImplementedError('unassignMachine')

    def wakeup(self, host: 'HostInfo', verify_ssl: bool = False) -> None:
        if host.mac:
            wake_on_land_endpoint = self.parent().wake_on_lan_endpoint(host)
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
