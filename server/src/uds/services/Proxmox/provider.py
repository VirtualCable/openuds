#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import typing

from django.utils.translation import gettext_noop as _

from uds.core import services, types
from uds.core.ui import gui
from uds.core.util import validators
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached
from uds.core.util.unique_id_generator import UniqueIDGenerator
from uds.core.util.unique_mac_generator import UniqueMacGenerator

from . import client
from .service import ProxmoxLinkedService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module

logger = logging.getLogger(__name__)

CACHE_TIME_FOR_SERVER = 1800
MAX_VM_ID = 999999999


class ProxmoxProvider(
    services.ServiceProvider
):  # pylint: disable=too-many-public-methods
    offers = [ProxmoxLinkedService]
    typeName = _('Proxmox Platform Provider')
    typeType = 'ProxmoxPlatform'
    typeDescription = _('Proxmox platform service provider')
    iconFile = 'provider.png'

    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('Proxmox Server IP or Hostname'),
        required=True,
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        order=2,
        tooltip=_('Proxmox API port (default is 8006)'),
        required=True,
        default=8006,
    )

    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=3,
        tooltip=_(
            'User with valid privileges on Proxmox, (use "user@authenticator" form)'
        ),
        required=True,
        default='root@pam',
    )
    password = gui.PasswordField(
        lenth=32,
        label=_('Password'),
        order=4,
        tooltip=_('Password of the user of Proxmox'),
        required=True,
    )

    maxPreparingServices = gui.NumericField(
        length=3,
        label=_('Creation concurrency'),
        default=10,
        minValue=1,
        maxValue=65536,
        order=50,
        tooltip=_('Maximum number of concurrently creating VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    maxRemovingServices = gui.NumericField(
        length=3,
        label=_('Removal concurrency'),
        default=5,
        minValue=1,
        maxValue=65536,
        order=51,
        tooltip=_('Maximum number of concurrently removing VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    timeout = gui.NumericField(
        length=3,
        label=_('Timeout'),
        default=20,
        order=90,
        tooltip=_('Timeout in seconds of connection to Proxmox'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    startVmId = gui.NumericField(
        length=3,
        label=_('Starting VmId'),
        default=10000,
        minValue=10000,
        maxValue=100000,
        order=91,
        tooltip=_('Starting machine id on proxmox'),
        required=True,
        readonly=True,
        tab=types.ui.Tab.ADVANCED,
    )

    macsRange = gui.TextField(
        length=36,
        label=_('Macs range'),
        default='52:54:00:00:00:00-52:54:00:FF:FF:FF',
        order=91,
        readonly=False,
        tooltip=_(
            'Range of valid macs for created machines. Any value accepted by Proxmox is valid here.'
        ),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )


    # Own variables
    _api: typing.Optional[client.ProxmoxClient] = None
    _vmid_generator: UniqueIDGenerator
    _macs_generator: UniqueMacGenerator

    def _getApi(self) -> client.ProxmoxClient:
        """
        Returns the connection API object
        """
        if self._api is None:
            self._api = client.ProxmoxClient(
                self.host.value,
                self.port.num(),
                self.username.value,
                self.password.value,
                self.timeout.num(),
                False,
                self.cache,
            )

        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.timeout.value = validators.validateTimeout(self.timeout.value)
            logger.debug(self.host.value)

        # All proxmox use same UniqueId generator
        self._vmid_generator = UniqueIDGenerator('vmid', 'proxmox', 'proxmox')

    def testConnection(self) -> bool:
        """
        Test that conection to Proxmox server is fine

        Returns

            True if all went fine, false if id didn't
        """

        return self._getApi().test()

    def listMachines(self) -> typing.List[client.types.VMInfo]:
        return self._getApi().listVms()

    def getMachineInfo(
        self, vmId: int, poolId: typing.Optional[str] = None
    ) -> client.types.VMInfo:
        return self._getApi().getVMPoolInfo(vmId, poolId, force=True)

    def getMachineConfiguration(self, vmId: int) -> client.types.VMConfiguration:
        return self._getApi().getVmConfiguration(vmId, force=True)

    def getStorageInfo(self, storageId: str, node: str) -> client.types.StorageInfo:
        return self._getApi().getStorage(storageId, node)

    def listStorages(
        self, node: typing.Optional[str]
    ) -> typing.List[client.types.StorageInfo]:
        return self._getApi().listStorages(node=node, content='images')

    def listPools(self) -> typing.List[client.types.PoolInfo]:
        return self._getApi().listPools()

    def makeTemplate(self, vmId: int) -> None:
        return self._getApi().convertToTemplate(vmId)

    def cloneMachine(
        self,
        vmId: int,
        name: str,
        description: typing.Optional[str],
        linkedClone: bool,
        toNode: typing.Optional[str] = None,
        toStorage: typing.Optional[str] = None,
        toPool: typing.Optional[str] = None,
        mustHaveVGPUS: typing.Optional[bool] = None,
    ) -> client.types.VmCreationResult:
        return self._getApi().cloneVm(
            vmId,
            self.getNewVmId(),
            name,
            description,
            linkedClone,
            toNode,
            toStorage,
            toPool,
            mustHaveVGPUS,
        )
        

    def startMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().startVm(vmId)

    def stopMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().stopVm(vmId)

    def resetMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().resetVm(vmId)

    def suspendMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().suspendVm(vmId)

    def shutdownMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().shutdownVm(vmId)

    def removeMachine(self, vmId: int) -> client.types.UPID:
        return self._getApi().deleteVm(vmId)

    def getTaskInfo(self, node: str, upid: str) -> client.types.TaskStatus:
        return self._getApi().getTask(node, upid)

    def enableHA(
        self, vmId: int, started: bool = False, group: typing.Optional[str] = None
    ) -> None:
        self._getApi().enableVmHA(vmId, started, group)

    def setVmMac(
        self, vmId: int, macAddress: str
    ) -> None:
        self._getApi().setVmMac(vmId, macAddress)

    def disableHA(self, vmId: int) -> None:
        self._getApi().disableVmHA(vmId)

    def setProtection(
        self, vmId: int, node: typing.Optional[str] = None, protection: bool = False
    ) -> None:
        self._getApi().setProtection(vmId, node, protection)

    def listHaGroups(self) -> typing.List[str]:
        return self._getApi().listHAGroups()

    def getConsoleConnection(
        self, machineId: str
    ) -> typing.Optional[typing.MutableMapping[str, typing.Any]]:
        return self._getApi().getConsoleConnection(machineId)

    def getNewVmId(self) -> int:
        while True:  # look for an unused VmId
            vmId = self._vmid_generator.get(self.startVmId.num(), MAX_VM_ID)
            if self._getApi().isVMIdAvailable(vmId):
                return vmId
            # All assigned VMId will be left as unusable on UDS until released by time (3 months)

    @cached('reachable', Cache.SHORT_VALIDITY)
    def isAvailable(self) -> bool:
        return self._getApi().test()

    def getMacRange(self) -> str:
        return self.macsRange.value

    @staticmethod
    def test(env: 'Environment', data: 'Module.ValuesType') -> typing.List[typing.Any]:
        """
        Test Proxmox Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..

        """
        # try:
        #    # We instantiate the provider, but this may fail...
        #    instance = Provider(env, data)
        #    logger.debug('Methuselah has {0} years and is {1} :-)'
        #                 .format(instance.methAge.value, instance.methAlive.value))
        # except exceptions.ValidationException as e:
        #    # If we say that meth is alive, instantiation will
        #    return [False, str(e)]
        # except Exception as e:
        #    logger.exception("Exception caugth!!!")
        #    return [False, str(e)]
        # return [True, _('Nothing tested, but all went fine..')]
        prox = ProxmoxProvider(env, data)
        if prox.testConnection() is True:
            return [True, 'Test successfully passed']

        return [False, _("Connection failed. Check connection params")]
