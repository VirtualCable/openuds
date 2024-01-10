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
import pickle
import random  # nosec # Pickle use is controled by app, never by non admin user input
import typing
import collections.abc

from django.db import transaction
from django.utils.translation import gettext, gettext_lazy as _

from uds.core import exceptions, services, types
from uds.core.ui import gui
from uds.core.util import ensure, log, net
from uds.core.util.model import sql_stamp_seconds

from .deployment import IPMachineDeployed
from .service_base import IPServiceBase

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

    ipList = gui.EditableListField(
        label=typing.cast(str, _('List of servers')),
        tooltip=typing.cast(str, _('List of servers available for this service')),
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
    skipTimeOnFailure = gui.NumericField(
        length=6,
        label=typing.cast(str, _('Skip time')),
        default=0,
        order=2,
        tooltip=typing.cast(str, _('If a host fails to check, skip it for this time (in minutes).')),
        minValue=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    maxSessionForMachine = gui.NumericField(
        length=3,
        label=typing.cast(str, _('Max session per machine')),
        default=0,
        order=3,
        tooltip=typing.cast(
            str,
            _(
                'Maximum session duration before UDS thinks this machine got locked and releases it (hours). 0 means "never".'
            ),
        ),
        minValue=0,
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    lockByExternalAccess = gui.CheckBoxField(
        label=typing.cast(str, _('Lock machine by external access')),
        tooltip=typing.cast(str, _('If checked, UDS will lock the machine if it is accesed from outside UDS.')),
        default=False,
        order=4,
        tab=types.ui.Tab.ADVANCED,
    )
    useRandomIp = gui.CheckBoxField(
        label=typing.cast(str, _('Use random IP')),
        tooltip=typing.cast(str, _('If checked, UDS will use a random IP from the list of servers.')),
        default=False,
        order=5,
        tab=types.ui.Tab.ADVANCED,
    )

    # Description of service
    type_name = typing.cast(str, _('Static Multiple IP'))
    type_type = 'IPMachinesService'
    type_description = typing.cast(str, _('This service provides access to POWERED-ON Machines by IP'))
    icon_file = 'machines.png'

    uses_cache = False  # Cache are running machine awaiting to be assigned
    uses_cache_l2 = False  # L2 Cache are running machines in suspended state
    needs_manager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    must_assign_manually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    user_service_type = IPMachineDeployed

    services_type_provided = types.services.ServiceType.VDI

    _ips: list[str] = []
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
                if not net.is_valid_host(v.split(';')[0]):  # Get only IP/hostname
                    raise exceptions.validation.ValidationError(
                        gettext('Invalid value detected on servers list: "{}"').format(v)
                    )
            self._ips = [
                '{}~{}'.format(str(ip).strip(), i) for i, ip in enumerate(values['ipList']) if str(ip).strip()
            ]  # Allow duplicates right now
            # Current stored data, if it exists
            d = self.storage.read_from_db('ips')
            old_ips = pickle.loads(d) if d and isinstance(d, bytes) else []  # nosec: pickle is safe here
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
        self._lockByExternalAccess = self.lockByExternalAccess.as_bool()
        self._useRandomIp = self.useRandomIp.as_bool()

    def get_token(self):
        return self._token or None

    def get_dict_of_values(self) -> gui.ValuesDictType:
        ips = (i.split('~')[0] for i in self._ips)
        return {
            'ipList': ensure.is_list(ips),
            'token': self._token,
            'port': str(self._port),
            'skipTimeOnFailure': str(self._skipTimeOnFailure),
            'maxSessionForMachine': str(self._maxSessionForMachine),
            'lockByExternalAccess': gui.from_bool(self._lockByExternalAccess),
            'useRandomIp': gui.from_bool(self._useRandomIp),
        }

    def marshal(self) -> bytes:
        self.storage.save_to_db('ips', pickle.dumps(self._ips))
        return b'\0'.join(
            [
                b'v7',
                self._token.encode(),
                str(self._port).encode(),
                str(self._skipTimeOnFailure).encode(),
                str(self._maxSessionForMachine).encode(),
                gui.from_bool(self._lockByExternalAccess).encode(),
                gui.from_bool(self._useRandomIp).encode(),
            ]
        )

    def unmarshal(self, data: bytes) -> None:
        values: list[bytes] = data.split(b'\0')
        d = self.storage.read_from_db('ips')
        if isinstance(d, bytes):
            self._ips = pickle.loads(d)  # nosec: pickle is safe here
        elif isinstance(d, str):  # "legacy" saved elements
            self._ips = pickle.loads(d.encode('utf8'))  # nosec: pickle is safe here
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
                self._lockByExternalAccess = gui.as_bool(values[5].decode())
            if values[0] in (b'v7',):
                self._useRandomIp = gui.as_bool(values[6].decode())

        # Sets maximum services for this
        self.max_user_services = len(self._ips)

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
            now = sql_stamp_seconds()

            # Reorder ips, so we do not always get the same one if requested
            allIps = self._ips[:]
            if self._useRandomIp:
                random.shuffle(allIps)

            for ip in allIps:
                theIP = IPServiceBase.getIp(ip)
                theMAC = IPServiceBase.getMac(ip)
                locked = self.storage.get_unpickle(theIP)
                if self.canBeUsed(locked, now):
                    if (
                        self._port > 0
                        and self._skipTimeOnFailure > 0
                        and self.cache.get('port{}'.format(theIP))
                    ):
                        continue  # The check failed not so long ago, skip it...
                    self.storage.put_pickle(theIP, now)
                    # Is WOL enabled?
                    wolENABLED = bool(self.parent().wolURL(theIP, theMAC))
                    # Now, check if it is available on port, if required...
                    if self._port > 0 and not wolENABLED:  # If configured WOL, check is a nonsense
                        if net.test_connectivity(theIP, self._port, timeOut=0.5) is False:
                            # Log into logs of provider, so it can be "shown" on services logs
                            self.parent().do_log(
                                log.LogLevel.WARNING,
                                f'Host {theIP} not accesible on port {self._port}',
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

    def enumerate_assignables(self):
        return [(ip, ip.split('~')[0]) for ip in self._ips if self.storage.read_from_db(ip) is None]

    def assign_from_assignables(
        self,
        assignableId: str,
        user: 'models.User',
        userDeployment: 'services.UserService',
    ) -> str:
        userServiceInstance: IPMachineDeployed = typing.cast(IPMachineDeployed, userDeployment)
        theIP = IPServiceBase.getIp(assignableId)
        theMAC = IPServiceBase.getMac(assignableId)

        now = sql_stamp_seconds()
        locked = self.storage.get_unpickle(theIP)
        if self.canBeUsed(locked, now):
            self.storage.put_pickle(theIP, now)
            if theMAC:
                theIP += ';' + theMAC
            return userServiceInstance.assign(theIP)

        return userServiceInstance.error('IP already assigned')

    def process_login(self, id: str, remote_login: bool) -> None:
        '''
        Process login for a machine not assigned to any user.
        '''
        logger.debug('Processing login for %s: %s', self, id)

        # Locate the IP on the storage
        theIP = IPServiceBase.getIp(id)
        now = sql_stamp_seconds()
        locked: typing.Union[None, str, int] = self.storage.get_unpickle(theIP)
        if self.canBeUsed(locked, now):
            self.storage.put_pickle(theIP, str(now))  # Lock it

    def process_logout(self, id: str, remote_login: bool) -> None:
        '''
        Process logout for a machine not assigned to any user.
        '''
        logger.debug('Processing logout for %s: %s', self, id)
        # Locate the IP on the storage
        theIP = IPServiceBase.getIp(id)
        locked: typing.Union[None, str, int] = self.storage.get_unpickle(theIP)
        # If locked is str, has been locked by processLogin so we can unlock it
        if isinstance(locked, str):
            self.unassignMachine(id)
        # If not proccesed by login, we cannot release it

    def notify_initialization(self, id: str) -> None:
        '''
        Notify that a machine has been initialized.
        Normally, this means that
        '''
        logger.debug('Notify initialization for %s: %s', self, id)
        self.unassignMachine(id)

    def get_valid_id(self, idsList: collections.abc.Iterable[str]) -> typing.Optional[str]:
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
