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
import requests
import logging
import typing

from uds.core import services

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from . import provider

class IPServiceBase(services.Service):

    @staticmethod
    def getIp(ipData: str) -> str:
        return ipData.split('~')[0].split(';')[0]

    @staticmethod
    def getMac(ipData: str) -> typing.Optional[str]:
        try:
            return ipData.split('~')[0].split(';')[1]
        except Exception:
            return None

    def parent(self) -> 'provider.PhysicalMachinesProvider':
        return typing.cast('provider.PhysicalMachinesProvider', super().parent())

    def getUnassignedMachine(self) -> typing.Optional[str]:
        raise NotADirectoryError('getUnassignedMachine')

    def unassignMachine(self, ip: str) -> None:
        raise NotADirectoryError('unassignMachine')

    def wakeup(self, ip: str, mac: typing.Optional[str]) -> None:
        if mac:
            wolurl = self.parent().wolURL(ip).replace('{MAC}', mac or '').replace('{IP}', ip or '')
            if wolurl:
                logger.info('Launching WOL: %s', wolurl)
                try:
                    requests.get(wolurl, verify=False)
                    # logger.debug('Result: %s', result)
                except Exception as e:
                    logger.error('Error on WOL: %s', e)
