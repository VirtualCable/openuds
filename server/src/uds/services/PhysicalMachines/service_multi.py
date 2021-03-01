# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import pickle
import logging
import typing

from django.utils.translation import ugettext_lazy as _
from django.db import transaction

from uds.core.ui import gui
from uds.core.util import log
from uds.core.util import connection
from uds.core.services import types as serviceTypes

from .deployment import IPMachineDeployed
from .service_base import IPServiceBase

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import Module
    from uds.core import services

logger = logging.getLogger(__name__)


class IPMachinesService(IPServiceBase):
    # Gui
    token = gui.TextField(
        order=1,
        label=_('Service Token'),
        length=16,
        tooltip=_('Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'),
        defvalue='',
        required=False,
        rdonly=False
    )

    ipList = gui.EditableList(label=_('List of servers'), tooltip=_('List of servers available for this service'))

    port = gui.NumericField(length=5, label=_('Check Port'), defvalue='0', order=2, tooltip=_('If non zero, only hosts responding to connection on that port will be served.'), required=True, tab=gui.ADVANCED_TAB)
    skipTimeOnFailure = gui.NumericField(length=6, label=_('Skip time'), defvalue='0', order=2, tooltip=_('If a host fails to check, skip it for this time (in minutes).'), minValue=0, required=True, tab=gui.ADVANCED_TAB)

    # Description of service
    typeName = _('Static Multiple IP')
    typeType = 'IPMachinesService'
    typeDescription = _('This service provides access to POWERED-ON Machines by IP')
    iconFile = 'machines.png'

    # Characteristics of service
    maxDeployed = -1  # If the service provides more than 1 "provided service" (-1 = no limit, 0 = ???? (do not use it!!!), N = max number to deploy
    usesCache = False  # Cache are running machine awaiting to be assigned
    usesCache_L2 = False  # L2 Cache are running machines in suspended state
    needsManager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    mustAssignManually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    deployedType = IPMachineDeployed

    servicesTypeProvided = (serviceTypes.VDI,)

    _ips: typing.List[str] = []
    _token: str = ''
    _port: int = 0
    _skipTimeOnFailure: int = 0

    def initialize(self, values: 'Module.ValuesType') -> None:
        if values is None:
            return

        if values.get('ipList', None) is None:
            self._ips = []
        else:
            self._ips = ['{}~{}'.format(str(ip).strip(), i) for i, ip in enumerate(values['ipList']) if str(ip).strip()]  # Allow duplicates right now
            active = {v for v in values['ipList']}
            # self._ips.sort()
            # Remove non existing "locked" ips from storage now
            skipKey = self.storage.getKey('ips')
            with transaction.atomic():
                for key, data, _ in self.storage.filter(forUpdate=True):
                    if key == skipKey: # Avoid "ips" key
                        continue
                    # If not in current active list of ips, remove it
                    if data.decode() not in active:
                        logger.info('IP %s locked but not in active list. Removed', data.decode())
                        self.storage.remove(data.decode())

        self._token = self.token.value.strip()
        self._port = self.port.value
        self._skipTimeOnFailure = self.skipTimeOnFailure.num()

    def getToken(self):
        return self._token or None

    def valuesDict(self) -> gui.ValuesDictType:
        ips = (i.split('~')[0] for i in self._ips)

        return {'ipList': gui.convertToList(ips), 'token': self._token, 'port': str(self._port), 'skipTimeOnFailure': str(self._skipTimeOnFailure) }

    def marshal(self) -> bytes:
        self.storage.saveData('ips', pickle.dumps(self._ips))
        return b'\0'.join([b'v4', self._token.encode(), str(self._port).encode(), str(self._skipTimeOnFailure).encode()])

    def unmarshal(self, data: bytes) -> None:
        values: typing.List[bytes] = data.split(b'\0')
        d = self.storage.readData('ips')
        if isinstance(d, bytes):
            self._ips = pickle.loads(d)
        elif isinstance(d, str):  # "legacy" saved elements
            self._ips = pickle.loads(d.encode('utf8'))
            self.marshal()  # Ensure now is bytes..
        else:
            self._ips = []
        if values[0] != b'v1':
            self._token = values[1].decode()
            if values[0] in (b'v3', b'v4'):
                self._port = int(values[2].decode())
            if values[0] == b'v4':
                self._skipTimeOnFailure = int(values[3].decode())

        # Sets maximum services for this
        self.maxDeployed = len(self._ips)

    def getUnassignedMachine(self) -> typing.Optional[str]:
        # Search first unassigned machine
        try:
            for ip in self._ips:
                theIP = ip.split('~')[0]
                if self.storage.readData(theIP) is None:
                    if self._port > 0 and self._skipTimeOnFailure > 0 and self.cache.get('port{}'.format(theIP)):
                        continue  # The check failed not so long ago, skip it...
                    self.storage.saveData(theIP, theIP)
                    # Now, check if it is available on port, if required...
                    if self._port > 0:
                        if connection.testServer(theIP, self._port, timeOut=0.5) is False:
                            # Log into logs of provider, so it can be "shown" on services logs
                            self.parent().doLog(log.WARN, 'Host {} not accesible on port {}'.format(theIP, self._port))
                            logger.warning('Static Machine check on %s:%s failed. Will be ignored for %s minutes.', theIP, self._port, self._skipTimeOnFailure)
                            self.storage.remove(theIP)  # Return Machine to pool
                            # Keep last check time
                            if self._skipTimeOnFailure > 0:
                                self.cache.put('port{}'.format(theIP), '1', validity=self._skipTimeOnFailure*60)
                            continue
                    return theIP
            return None
        except Exception:
            logger.exception("Exception at getUnassignedMachine")
            return None

    def unassignMachine(self, ip: str) -> None:
        try:
            self.storage.remove(ip)
        except Exception:
            logger.exception("Exception at getUnassignedMachine")

    def listAssignables(self):
        return [(ip, ip.split('~')[0]) for ip in self._ips if self.storage.readData(ip) is None]

    def assignFromAssignables(self, assignableId: str, user: 'models.User', userDeployment: 'services.UserDeployment') -> str:
        userServiceInstance: IPMachineDeployed = typing.cast(IPMachineDeployed, userDeployment)
        theIP = assignableId.split('~')[0]
        if self.storage.readData(theIP) is None:
            self.storage.saveData(theIP, theIP)
            return userServiceInstance.assign(theIP)
        return userServiceInstance.error('IP already assigned')
