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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import re
import logging
import typing

from django.utils.translation import ugettext_noop as _

from uds.core.transports import protocols
from uds.core.services import Service, types as serviceTypes
from uds.core.util import validators
from uds.core.util import tools
from uds.core.ui import gui

from .publication import ProxmoxPublication
from .deployment import ProxmoxDeployment
from . import helpers

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import ProxmoxProvider
    from . import client
    from uds.core import Module

logger = logging.getLogger(__name__)


class ProxmoxLinkedService(Service):  # pylint: disable=too-many-public-methods
    """
    Proxmox Linked clones service. This is based on creating a template from selected vm, and then use it to
    """
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('Proxmox Linked Clone')
    # : Type used internally to identify this provider
    typeType = 'ProxmoxLinkedService'
    # : Description shown at administration interface for this provider
    typeDescription = _('Proxmox Services based on templates and COW (experimental)')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    iconFile = 'service.png'

    # Functional related data

    # : If the service provides more than 1 "deployed user" (-1 = no limit,
    # : 0 = ???? (do not use it!!!), N = max number to deploy
    maxDeployed = -1
    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is usesCache is True, you will need also
    # : set publicationType, do take care about that!
    usesCache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cacheTooltip = _('Number of desired machines to keep running waiting for a user')
    # : If we need to generate a "Level 2" cache for this service (i.e., L1
    # : could be running machines and L2 suspended machines)
    usesCache_L2 = True
    # : Tooltip shown to user when this item is pointed at admin interface, None
    # : also because we don't use it
    cacheTooltip_L2 = _('Number of desired VMs to keep stopped waiting for use')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = True
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False
    canReset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = ProxmoxPublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = ProxmoxDeployment

    allowedProtocols = protocols.GENERIC # + (protocols.SPICE,)
    servicesTypeProvided = (serviceTypes.VDI,)

    pool = gui.ChoiceField(
        label=_("Pool"),
        order=1,
        tooltip=_('Pool that will contain UDS created vms'),
        # tab=_('Machine'),
        # required=True,
        defvalue=''
    )

    ha = gui.ChoiceField(
        label=_('HA'),
        order=2,
        tooltip=_('Select if HA is enabled and HA group for machines of this service'),
        rdonly=True
    )

    guestShutdown = gui.CheckBoxField(
        label=_('Try SOFT Shutdown first'),
        defvalue=gui.FALSE,
        order=103,
        tooltip=_(
            'If active, UDS will try to shutdown (soft) the machine using VMWare Guest Tools. Will delay 30 seconds the power off of hanged machines.'
        ),
    )

    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        fills={
            'callbackName': 'pmFillResourcesFromMachine',
            'function': helpers.getStorage,
            'parameters': ['machine', 'ov', 'ev']
        },
        tooltip=_('Service base machine'),
        tab=_('Machine'),
        required=True
    )

    datastore = gui.ChoiceField(
        label=_("Storage"),
        rdonly=False,
        order=111,
        tooltip=_('Storage for publications & machines.'),
        tab=_('Machine'),
        required=True
    )

    baseName = gui.TextField(
        label=_('Machine Names'),
        rdonly=False,
        order=115,
        tooltip=_('Base name for clones from this machine'),
        tab=_('Machine'),
        required=True
    )

    lenName = gui.NumericField(
        length=1,
        label=_('Name Length'),
        defvalue=5,
        order=116,
        tooltip=_('Size of numeric part for the names of these machines'),
        tab=_('Machine'),
        required=True
    )

    ov = gui.HiddenField(value=None)
    ev = gui.HiddenField(value=None)  # We need to keep the env so we can instantiate the Provider

    def initialize(self, values: 'Module.ValuesType') -> None:
        if values:
            self.baseName.value = validators.validateHostname(self.baseName.value, 15, asPattern=True)
            # if int(self.memory.value) < 128:
            #     raise Service.ValidationException(_('The minimum allowed memory is 128 Mb'))

    def initGui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.ov.defValue = self.parent().serialize()
        self.ev.defValue = self.parent().env.key

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.setValues([gui.choiceItem(str(m.vmid), '{}\\{}'.format(m.node, m.name or m.vmid)) for m in self.parent().listMachines() if m.name and m.name[:3] != 'UDS'])
        self.pool.setValues([gui.choiceItem('', _('None'))] + [gui.choiceItem(p.poolid, p.poolid) for p in self.parent().listPools()])
        self.ha.setValues(
            [
                gui.choiceItem('', _('Enabled')), gui.choiceItem('__', _('Disabled'))
            ] + 
            [
                gui.choiceItem(group, group) for group in self.parent().listHaGroups()
            ]
        )

    def parent(self) -> 'ProxmoxProvider':
        return typing.cast('ProxmoxProvider', super().parent())

    def sanitizeVmName(self, name: str) -> str:
        """
        Proxmox only allows machine names with [a-zA-Z0-9_-]
        """
        return re.sub("[^a-zA-Z0-9_-]", "-", name)

    def makeTemplate(self, vmId: int) -> None:
        self.parent().makeTemplate(vmId)

    def cloneMachine(self, name: str, description: str, vmId: int = -1) -> 'client.types.VmCreationResult':
        name = self.sanitizeVmName(name)
        pool = self.pool.value or None
        if vmId == -1:  # vmId == -1 if cloning for template
            return self.parent().cloneMachine(
                self.machine.value,
                name,
                description,
                linkedClone=False,
                toStorage=self.datastore.value,
                toPool=pool
            )

        return self.parent().cloneMachine(
            vmId,
            name,
            description,
            linkedClone=True,
            toStorage=self.datastore.value,
            toPool=pool
        )

    def getMachineInfo(self, vmId: int) -> 'client.types.VMInfo':
        return self.parent().getMachineInfo(vmId)

    def getMac(self, vmId: int) -> str:
        config = self.parent().getMachineConfiguration(vmId)
        return config.networks[0].mac

    def getTaskInfo(self, node: str, upid: str) -> 'client.types.TaskStatus':
        return self.parent().getTaskInfo(node, upid)

    def startMachine(self,vmId: int) -> 'client.types.UPID':
        return self.parent().startMachine(vmId)

    def stopMachine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().stopMachine(vmId)

    def resetMachine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().resetMachine(vmId)

    def suspendMachine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().suspendMachine(vmId)

    def shutdownMachine(self, vmId: int) -> 'client.types.UPID':
        return self.parent().shutdownMachine(vmId)

    def removeMachine(self, vmId: int) -> 'client.types.UPID':
        # First, remove from HA if needed
        self.disableHA(vmId)
        # And remove it
        return self.parent().removeMachine(vmId)

    def enableHA(self, vmId: int, started: bool = False) -> None:
        if self.ha.value == '__':
            return
        self.parent().enableHA(vmId, started, self.ha.value or None)

    def disableHA(self, vmId: int) -> None:
        if self.ha.value == '__':
            return
        self.parent().disableHA(vmId)

    def setProtection(self, vmId: int, node: typing.Optional[str] = None, protection: bool=False) -> None:
        self.parent().setProtection(vmId, node, protection)

    def getBaseName(self) -> str:
        return self.baseName.value

    def getLenName(self) -> int:
        return int(self.lenName.value)

    def isHaEnabled(self) -> bool:
        return self.ha.isTrue()

    def tryGracelyShutdown(self) -> bool:
        return self.guestShutdown.isTrue()

    def getConsoleConnection(self, machineId: str) -> typing.Optional[typing.MutableMapping[str, typing.Any]]:
        return self.parent().getConsoleConnection(machineId)
