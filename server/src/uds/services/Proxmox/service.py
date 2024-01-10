#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import re
import typing
import collections.abc

from django.utils.translation import gettext_noop as _
from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators, log
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import helpers
from .deployment import ProxmoxDeployment
from .publication import ProxmoxPublication

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module

    from . import client
    from .provider import ProxmoxProvider

logger = logging.getLogger(__name__)


class ProxmoxLinkedService(services.Service):  # pylint: disable=too-many-public-methods
    """
    Proxmox Linked clones service. This is based on creating a template from selected vm, and then use it to
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Proxmox Linked Clone')
    # : Type used internally to identify this provider
    type_type = 'ProxmoxLinkedService'
    # : Description shown at administration interface for this provider
    type_description = _('Proxmox Services based on templates and COW (experimental)')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'service.png'

    # Functional related data

    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is uses_cache is True, you will need also
    # : set publication_type, do take care about that!
    uses_cache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cache_tooltip = _('Number of desired machines to keep running waiting for a user')
    # : If we need to generate a "Level 2" cache for this service (i.e., L1
    # : could be running machines and L2 suspended machines)
    uses_cache_l2 = True
    # : Tooltip shown to user when this item is pointed at admin interface, None
    # : also because we don't use it
    cache_tooltip_l2 = _('Number of desired VMs to keep stopped waiting for use')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needs_manager = True
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    must_assign_manually = False
    can_reset = True

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = ProxmoxPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = ProxmoxDeployment

    allowed_protocols = types.transports.Protocol.generic_vdi(types.transports.Protocol.SPICE)
    services_type_provided = types.services.ServiceType.VDI



    pool = gui.ChoiceField(
        label=_("Pool"),
        order=1,
        tooltip=_('Pool that will contain UDS created vms'),
        # tab=_('Machine'),
        # required=True,
        default='',
    )

    ha = gui.ChoiceField(
        label=_('HA'),
        order=2,
        tooltip=_('Select if HA is enabled and HA group for machines of this service'),
        readonly=True,
    )

    guestShutdown = gui.CheckBoxField(
        label=_('Try SOFT Shutdown first'),
        default=False,
        order=103,
        tooltip=_(
            'If active, UDS will try to shutdown (soft) the machine using VMWare Guest Tools. Will delay 30 seconds the power off of hanged machines.'
        ),
    )

    machine = gui.ChoiceField(
        label=_("Base Machine"),
        order=110,
        fills={
            'callback_name': 'pmFillResourcesFromMachine',
            'function': helpers.getStorage,
            'parameters': ['machine', 'ov', 'ev'],
        },
        tooltip=_('Service base machine'),
        tab=_('Machine'),
        required=True,
    )

    datastore = gui.ChoiceField(
        label=_("Storage"),
        readonly=False,
        order=111,
        tooltip=_('Storage for publications & machines.'),
        tab=_('Machine'),
        required=True,
    )

    gpu = gui.ChoiceField(
        label=_("GPU Availability"),
        readonly=False,
        order=112,
        choices={
            '0': _('Do not check'),
            '1': _('Only if available'),
            '2': _('Only if NOT available'),
        },
        tooltip=_('Storage for publications & machines.'),
        tab=_('Machine'),
        required=True,
    )

    baseName = gui.TextField(
        label=_('Machine Names'),
        readonly=False,
        order=115,
        tooltip=_('Base name for clones from this machine'),
        tab=_('Machine'),
        required=True,
    )

    lenName = gui.NumericField(
        length=1,
        label=_('Name Length'),
        default=5,
        order=116,
        tooltip=_('Size of numeric part for the names of these machines'),
        tab=_('Machine'),
        required=True,
    )

    ov = gui.HiddenField(value=None)
    ev = gui.HiddenField(
        value=None
    )  # We need to keep the env so we can instantiate the Provider

    def initialize(self, values: 'Module.ValuesType') -> None:
        if values:
            self.baseName.value = validators.validateBasename(
                self.baseName.value, length=self.lenName.num()
            )
            # if int(self.memory.value) < 128:
            #     raise exceptions.ValidationException(_('The minimum allowed memory is 128 Mb'))

    def init_gui(self) -> None:
        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.ov.value = self.parent().serialize()
        self.ev.value = self.parent().env.key

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.set_choices(
            [
                gui.choice_item(
                    str(m.vmid), f'{m.node}\\{m.name or m.vmid} ({m.vmid})'
                )
                for m in self.parent().listMachines()
                if m.name and m.name[:3] != 'UDS'
            ]
        )
        self.pool.set_choices(
            [gui.choice_item('', _('None'))]
            + [gui.choice_item(p.poolid, p.poolid) for p in self.parent().listPools()]
        )
        self.ha.set_choices(
            [gui.choice_item('', _('Enabled')), gui.choice_item('__', _('Disabled'))]
            + [gui.choice_item(group, group) for group in self.parent().listHaGroups()]
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

    def cloneMachine(
        self, name: str, description: str, vmId: int = -1
    ) -> 'client.types.VmCreationResult':
        name = self.sanitizeVmName(name)
        pool = self.pool.value or None
        if vmId == -1:  # vmId == -1 if cloning for template
            return self.parent().cloneMachine(
                self.machine.value,
                name,
                description,
                linkedClone=False,
                toStorage=self.datastore.value,
                toPool=pool,
            )

        return self.parent().cloneMachine(
            vmId,
            name,
            description,
            linkedClone=True,
            toStorage=self.datastore.value,
            toPool=pool,
            mustHaveVGPUS={'1': True, '2': False}.get(self.gpu.value, None),
        )

    def getMachineInfo(self, vmId: int) -> 'client.types.VMInfo':
        return self.parent().getMachineInfo(vmId, self.pool.value.strip())

    def getMac(self, vmId: int) -> str:
        config = self.parent().getMachineConfiguration(vmId)
        return config.networks[0].mac.lower()

    def getTaskInfo(self, node: str, upid: str) -> 'client.types.TaskStatus':
        return self.parent().getTaskInfo(node, upid)

    def startMachine(self, vmId: int) -> 'client.types.UPID':
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
        try:
            self.disableHA(vmId)
        except Exception as e:
            logger.warning('Exception disabling HA for vm %s: %s', vmId, e)
            self.do_log(level=log.LogLevel.WARNING, message=f'Exception disabling HA for vm {vmId}: {e}')
            
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

    def setProtection(
        self, vmId: int, node: typing.Optional[str] = None, protection: bool = False
    ) -> None:
        self.parent().setProtection(vmId, node, protection)

    def setVmMac(self, vmId: int, mac: str) -> None:
        self.parent().setVmMac(vmId, mac)

    def get_base_name(self) -> str:
        return self.baseName.value

    def getLenName(self) -> int:
        return int(self.lenName.value)

    def getMacRange(self) -> str:
        """
        Returns de selected mac range
        """
        return self.parent().getMacRange()

    def isHaEnabled(self) -> bool:
        return self.ha.as_bool()

    def tryGracelyShutdown(self) -> bool:
        return self.guestShutdown.as_bool()

    def getConsoleConnection(
        self, machineId: str
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        return self.parent().getConsoleConnection(machineId)

    @cached('reachable', consts.system.SHORT_CACHE_TIMEOUT)
    def is_avaliable(self) -> bool:
        return self.parent().isAvailable()
