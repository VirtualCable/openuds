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
import pickle
import logging
import typing
import random

from django.utils.translation import gettext, gettext_lazy as _
from django.db import transaction

from uds.models import getSqlDatetimeAsUnix
from uds.core.ui import gui
from uds.core.util import log
from uds.core.util import connection
from uds.core.util import net
from uds.core import services

from .deployment import IPMachineDeployed
from .service_base import IPServiceBase

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import Module

logger = logging.getLogger(__name__)


class IPMachinesService(IPServiceBase):
    # Gui
    token = gui.TextField(
        order=1,
        label=_('Service Token'),
        length=64,
        tooltip=_(
            'Service token that will be used by actors to communicate with service. Leave empty for persistent assignation.'
        ),
        defvalue='',
        required=False,
        rdonly=False,
    )

    ipList = gui.EditableList(
        label=_('List of servers'),
        tooltip=_('List of servers available for this service'),
    )

    port = gui.NumericField(
        length=5,
        label=_('Check Port'),
        defvalue='0',
        order=2,
        tooltip=_('If non zero, only hosts responding to connection on that port will be served.'),
        required=True,
        tab=gui.ADVANCED_TAB,
    )
    skipTimeOnFailure = gui.NumericField(
        length=6,
        label=_('Skip time'),
        defvalue='0',
        order=2,
        tooltip=_('If a host fails to check, skip it for this time (in minutes).'),
        minValue=0,
        required=True,
        tab=gui.ADVANCED_TAB,
    )

    maxSessionForMachine = gui.NumericField(
        length=3,
        label=_('Max session per machine'),
        defvalue='0',
        order=3,
        tooltip=_(
            'Maximum session duration before UDS thinks this machine got locked and releases it (hours). 0 means "never".'
        ),
        minValue=0,
        required=True,
        tab=gui.ADVANCED_TAB,
    )
    lockByExternalAccess = gui.CheckBoxField(
        label=_('Lock machine by external access'),
        tooltip=_('If checked, UDS will lock the machine if it is accesed from outside UDS.'),
        defvalue=False,
        order=4,
        tab=gui.ADVANCED_TAB,
    )
    useRandomIp = gui.CheckBoxField(
        label=_('Use random IP'),
        tooltip=_('If checked, UDS will use a random IP from the list of servers.'),
        defvalue=False,
        order=5,
        tab=gui.ADVANCED_TAB,
    )

    # Description of service
    typeName = _('Static Multiple IP')
    typeType = 'IPMachinesService'
    typeDescription = _('This service provides access to POWERED-ON Machines by IP')
    iconFile = 'machines.png'

    # Characteristics of service
    maxDeployed = (
        services.Service.UNLIMITED
    )  # If the service provides more than 1 "provided service" (-1 = no limit, 0 = ???? (do not use it!!!), N = max number to deploy
    usesCache = False  # Cache are running machine awaiting to be assigned
    usesCache_L2 = False  # L2 Cache are running machines in suspended state
    needsManager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    mustAssignManually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    deployedType = IPMachineDeployed

    servicesTypeProvided = (services.types.VDI,)

    _ips: typing.List[str] = []
    _token: str = ''
    _port: int = 0
    _skipTimeOnFailure: int = 0
    _maxSessionForMachine: int = 0
    _lockByExternalAccess: bool = False
    _useRandomIp: bool = False

    def initialize(self, values: 'Module.ValuesType') -> None:
        if values is None:
            return

        if values.get('ipList', None) is None:
            self._ips = []
        else:
            # Check that ips are valid
            for v in values['ipList']:
                if not net.isValidHost(v.split(';')[0]):  # Get only IP/hostname
                    raise IPServiceBase.ValidationException(
                        gettext('Invalid value detected on servers list: "{}"').format(v)
                    )
            self._ips = [
                '{}~{}'.format(str(ip).strip(), i) for i, ip in enumerate(values['ipList']) if str(ip).strip()
            ]  # Allow duplicates right now
            # Current stored data, if it exists
            d = self.storage.readData('ips')
            old_ips = pickle.loads(d) if d and isinstance(d, bytes) else []
            # dissapeared ones
            dissapeared = set(IPServiceBase.getIp(i.split('~')[0]) for i in old_ips) - set(
                i.split('~')[0] for i in self._ips
            )
            with transaction.atomic():
                for removable in dissapeared:
                    self.storage.remove(removable)

        self._token = self.token.value.strip()
        self._port = self.port.value
        self._skipTimeOnFailure = self.skipTimeOnFailure.num()
        self._maxSessionForMachine = self.maxSessionForMachine.num()
        self._lockByExternalAccess = self.lockByExternalAccess.isTrue()
        self._useRandomIp = self.useRandomIp.isTrue()

    def getToken(self):
        return self._token or None

    def valuesDict(self) -> gui.ValuesDictType:
        ips = (i.split('~')[0] for i in self._ips)

        return {
            'ipList': gui.convertToList(ips),
            'token': self._token,
            'port': str(self._port),
            'skipTimeOnFailure': str(self._skipTimeOnFailure),
            'maxSessionForMachine': str(self._maxSessionForMachine),
            'lockByExternalAccess': gui.boolToStr(self._lockByExternalAccess),
            'useRandomIp': gui.boolToStr(self._useRandomIp),
        }

    def marshal(self) -> bytes:
        self.storage.saveData('ips', pickle.dumps(self._ips))
        return b'\0'.join(
            [
                b'v7',
                self._token.encode(),
                str(self._port).encode(),
                str(self._skipTimeOnFailure).encode(),
                str(self._maxSessionForMachine).encode(),
                gui.boolToStr(self._lockByExternalAccess).encode(),
                gui.boolToStr(self._useRandomIp).encode(),
            ]
        )

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
            if values[0] in (b'v3', b'v4', b'v5', b'v6', b'v7'):
                self._port = int(values[2].decode())
            if values[0] in (b'v4', b'v5', b'v6', b'v7'):
                self._skipTimeOnFailure = int(values[3].decode())
            if values[0] in (b'v5', b'v6', b'v7'):
                self._maxSessionForMachine = int(values[4].decode())
            if values[0] in (b'v6', b'v7'):
                self._lockByExternalAccess = gui.strToBool(values[5].decode())
            if values[0] in (b'v7',):
                self._useRandomIp = gui.strToBool(values[6].decode())

        # Sets maximum services for this
        self.maxDeployed = len(self._ips)

    def canBeUsed(self, locked: typing.Optional[typing.Union[str, int]], now: int) -> int:
        # If _maxSessionForMachine is 0, it can be used only if not locked
        # (that is locked is None)
        locked = locked or 0
        if isinstance(locked, str) and not '.' in locked:  # Convert to int and treat it as a "locked" element
            locked = int(locked)

        if self._maxSessionForMachine <= 0:
            return not bool(locked)  # If locked is None, it can be used

        if not isinstance(locked, int):  # May have "old" data, that was the IP repeated
            return False

        if not locked or locked < now - self._maxSessionForMachine * 3600:
            return True

        return False

    def getUnassignedMachine(self) -> typing.Optional[str]:
        # Search first unassigned machine
        try:
            now = getSqlDatetimeAsUnix()

            # Reorder ips, so we do not always get the same one if requested
            allIps = self._ips[:]
            if self._useRandomIp:
                random.shuffle(allIps)
            for ip in allIps:
                theIP = IPServiceBase.getIp(ip)
                theMAC = IPServiceBase.getMac(ip)
                locked = self.storage.getPickle(theIP)
                if self.canBeUsed(locked, now):
                    if (
                        self._port > 0
                        and self._skipTimeOnFailure > 0
                        and self.cache.get('port{}'.format(theIP))
                    ):
                        continue  # The check failed not so long ago, skip it...
                    self.storage.putPickle(theIP, now)
                    # Is WOL enabled?
                    wolENABLED = bool(self.parent().wolURL(theIP, theMAC))
                    # Now, check if it is available on port, if required...
                    if self._port > 0 and not wolENABLED:  # If configured WOL, check is a nonsense
                        if connection.testServer(theIP, self._port, timeOut=0.5) is False:
                            # Log into logs of provider, so it can be "shown" on services logs
                            self.parent().doLog(
                                log.WARN,
                                'Host {} not accesible on port {}'.format(theIP, self._port),
                            )
                            logger.warning(
                                'Static Machine check on %s:%s failed. Will be ignored for %s minutes.',
                                theIP,
                                self._port,
                                self._skipTimeOnFailure,
                            )
                            self.storage.remove(theIP)  # Return Machine to pool
                            if self._skipTimeOnFailure > 0:
                                self.cache.put(
                                    'port{}'.format(theIP),
                                    '1',
                                    validity=self._skipTimeOnFailure * 60,
                                )
                            continue
                    if theMAC:
                        return theIP + ';' + theMAC
                    return theIP
            return None
        except Exception:
            logger.exception("Exception at getUnassignedMachine")
            return None

    def unassignMachine(self, ip: str) -> None:
        try:
            self.storage.remove(IPServiceBase.getIp(ip))
        except Exception:
            logger.exception("Exception at getUnassignedMachine")

    def listAssignables(self):
        return [(ip, ip.split('~')[0]) for ip in self._ips if self.storage.readData(ip) is None]

    def assignFromAssignables(
        self,
        assignableId: str,
        user: 'models.User',
        userDeployment: 'services.UserDeployment',
    ) -> str:
        userServiceInstance: IPMachineDeployed = typing.cast(IPMachineDeployed, userDeployment)
        theIP = IPServiceBase.getIp(assignableId)
        theMAC = IPServiceBase.getMac(assignableId)

        now = getSqlDatetimeAsUnix()
        locked = self.storage.getPickle(theIP)
        if self.canBeUsed(locked, now):
            self.storage.putPickle(theIP, now)
            if theMAC:
                theIP += ';' + theMAC
            return userServiceInstance.assign(theIP)

        return userServiceInstance.error('IP already assigned')

    def processLogin(self, id: str, remote_login: bool) -> None:
        '''
        Process login for a machine not assigned to any user.
        '''
        logger.debug('Processing login for %s: %s', self, id)

        # Locate the IP on the storage
        theIP = IPServiceBase.getIp(id)
        now = getSqlDatetimeAsUnix()
        locked: typing.Union[None, str, int] = self.storage.getPickle(theIP)
        if self.canBeUsed(locked, now):
            self.storage.putPickle(theIP, str(now))  # Lock it

    def processLogout(self, id: str, remote_login: bool) -> None:
        '''
        Process logout for a machine not assigned to any user.
        '''
        logger.debug('Processing logout for %s: %s', self, id)
        # Locate the IP on the storage
        theIP = IPServiceBase.getIp(id)
        locked: typing.Union[None, str, int] = self.storage.getPickle(theIP)
        # If locked is str, has been locked by processLogin so we can unlock it
        if isinstance(locked, str):
            self.unassignMachine(id)
        # If not proccesed by login, we cannot release it

    def notifyInitialization(self, id: str) -> None:
        '''
        Notify that a machine has been initialized.
        Normally, this means that
        '''
        logger.debug('Notify initialization for %s: %s', self, id)
        self.unassignMachine(id)

    def getValidId(self, idsList: typing.Iterable[str]) -> typing.Optional[str]:
        # If locking not allowed, return None
        if self._lockByExternalAccess is False:
            return None
        # Look for the first valid id on our list
        for ip in self._ips:
            theIP = IPServiceBase.getIp(ip)
            theMAC = IPServiceBase.getMac(ip)
            # If is managed by us
            if theIP in idsList or theMAC in idsList:
                return theIP + ';' + theMAC if theMAC else theIP
        return None
