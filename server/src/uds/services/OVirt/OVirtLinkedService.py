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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from django.utils.translation import ugettext_noop as _, ugettext
from uds.core.transports import protocols
from uds.core.services import Service, types as serviceTypes
from .OVirtPublication import OVirtPublication
from .OVirtLinkedDeployment import OVirtLinkedDeployment
from .Helpers import oVirtHelpers

from uds.core.ui import gui

import logging

__updated__ = '2016-02-26'

logger = logging.getLogger(__name__)


class OVirtLinkedService(Service):
    '''
    oVirt Linked clones service. This is based on creating a template from selected vm, and then use it to
    '''
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('oVirt/RHEV Linked Clone')
    # : Type used internally to identify this provider
    typeType = 'oVirtLinkedService'
    # : Description shown at administration interface for this provider
    typeDescription = _('oVirt Services based on templates and COW (experimental)')
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
    cacheTooltip_L2 = _('Number of desired machines to keep suspended waiting for use')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = True
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = OVirtPublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = OVirtLinkedDeployment

    allowedProtocols = protocols.GENERIC + (protocols.SPICE,)
    servicesTypeProvided = (serviceTypes.VDI,)

    # Now the form part
    machine = gui.ChoiceField(label=_("Base Machine"), order=1, tooltip=_('Service base machine'), required=True)
    cluster = gui.ChoiceField(label=_("Cluster"), order=2,
        fills={
            'callbackName': 'ovFillResourcesFromCluster',
            'function': oVirtHelpers.getResources,
            'parameters': ['cluster', 'ov', 'ev']
        },
        tooltip=_("Cluster to contain services"), required=True
    )

    datastore = gui.ChoiceField(
        label=_("Datastore Domain"),
        rdonly=False,
        order=3,
        tooltip=_('Datastore domain where to publish and put incrementals'),
        required=True
    )

    minSpaceGB = gui.NumericField(
        length=3,
        label=_('Reserved Space'),
        defvalue='32',
        order=4,
        tooltip=_('Minimal free space in GB'),
        required=True
    )

    memory = gui.NumericField(
        label=_("Memory (Mb)"),
        length=4,
        defvalue=512,
        rdonly=False,
        order=5,
        tooltip=_('Memory assigned to machines'),
        required=True
    )

    memoryGuaranteed = gui.NumericField(
        label=_("Memory Guaranteed (Mb)"),
        length=4,
        defvalue=256,
        rdonly=False,
        order=6,
        tooltip=_('Physical memory guaranteed to machines'),
        required=True
    )

    baseName = gui.TextField(
        label=_('Machine Names'),
        rdonly=False,
        order=6,
        tooltip=('Base name for clones from this machine'),
        required=True
    )

    lenName = gui.NumericField(
        length=1,
        label=_('Name Length'),
        defvalue=5,
        order=7,
        tooltip=_('Size of numeric part for the names of these machines (between 3 and 6)'),
        required=True
    )

    display = gui.ChoiceField(
        label=_('Display'),
        rdonly=False,
        order=8,
        tooltip=_('Display type (only for administration purposes)'),
        values=[
            gui.choiceItem('spice', 'Spice'),
            gui.choiceItem('vnc', 'Vnc')
        ],
        defvalue='1'  # Default value is the ID of the choicefield
    )

    ov = gui.HiddenField()
    ev = gui.HiddenField()  # We need to keep the env so we can instantiate the Provider

    def initialize(self, values):
        '''
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        '''
        if values is not None:
            length = int(self.lenName.value)
            if len(self.baseName.value) + length > 15:
                raise Service.ValidationException(_('The length of basename plus length must not be greater than 15'))
            if self.baseName.value.isdigit():
                raise Service.ValidationException(_('The machine name can\'t be only numbers'))
            if int(self.memory.value) < 256 or int(self.memoryGuaranteed.value) < 256:
                raise Service.ValidationException(_('The minimum allowed memory is 256 Mb'))
            if int(self.memoryGuaranteed.value) > int(self.memory.value):
                self.memoryGuaranteed.value = self.memory.value

        self.ov.value = self.parent().serialize()
        self.ev.value = self.parent().env.key

    def initGui(self):
        '''
        Loads required values inside
        '''

        # Here we have to use "default values", cause values aren't used at form initialization
        # This is that value is always '', so if we want to change something, we have to do it
        # at defValue
        self.ov.defValue = self.parent().serialize()
        self.ev.defValue = self.parent().env.key

        machines = self.parent().getMachines()
        vals = []
        for m in machines:
            vals.append(gui.choiceItem(m['id'], m['name']))

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.machine.setValues(vals)

        clusters = self.parent().getClusters()
        vals = []
        for c in clusters:
            vals.append(gui.choiceItem(c['id'], c['name']))

        self.cluster.setValues(vals)

    def datastoreHasSpace(self):
        # Get storages for that datacenter
        logger.debug('Checking datastore space for {0}'.format(self.datastore.value))
        info = self.parent().getStorageInfo(self.datastore.value)
        logger.debug('Datastore Info: {0}'.format(info))
        availableGB = info['available'] / (1024 * 1024 * 1024)
        if availableGB < self.minSpaceGB.num():
            raise Exception('Not enough free space available: (Needs at least {0} GB and there is only {1} GB '.format(self.minSpaceGB.num(), availableGB))

    def sanitizeVmName(self, name):
        '''
        Ovirt only allows machine names with [a-zA-Z0-9_-]
        '''
        import re
        return re.sub("[^a-zA-Z0-9_-]", "_", name)

    def makeTemplate(self, name, comments):
        '''
        Invokes makeTemplate from parent provider, completing params

        Args:
            name: Name to assign to template (must be previously "sanitized"
            comments: Comments (UTF-8) to add to template

        Returns:
            template Id of the template created

        Raises an exception if operation fails.
        '''

        # Checks datastore size
        # Get storages for that datacenter

        self.datastoreHasSpace()
        return self.parent().makeTemplate(name, comments, self.machine.value, self.cluster.value, self.datastore.value, self.display.value)

    def getTemplateState(self, templateId):
        '''
        Invokes getTemplateState from parent provider

        Args:
            templateId: templateId to remove

        Returns nothing

        Raises an exception if operation fails.
        '''
        return self.parent().getTemplateState(templateId)

    def deployFromTemplate(self, name, comments, templateId):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            displayType: 'vnc' or 'spice'. Display to use ad oVirt admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        '''
        logger.debug('Deploying from template {0} machine {1}'.format(templateId, name))
        self.datastoreHasSpace()
        return self.parent().deployFromTemplate(name, comments, templateId, self.cluster.value,
                                                self.display.value, int(self.memory.value), int(self.memoryGuaranteed.value))

    def removeTemplate(self, templateId):
        '''
        invokes removeTemplate from parent provider
        '''
        return self.parent().removeTemplate(templateId)

    def getMachineState(self, machineId):
        '''
        Invokes getMachineState from parent provider
        (returns if machine is "active" or "inactive"

        Args:
            machineId: If of the machine to get state

        Returns:
            one of this values:
             unassigned, down, up, powering_up, powered_down,
             paused, migrating_from, migrating_to, unknown, not_responding,
             wait_for_launch, reboot_in_progress, saving_state, restoring_state,
             suspended, image_illegal, image_locked or powering_down
             Also can return'unknown' if Machine is not known
        '''
        return self.parent().getMachineState(machineId)

    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().startMachine(machineId)

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().stopMachine(machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().suspendMachine(machineId)

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().removeMachine(machineId)

    def updateMachineMac(self, machineId, macAddres):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return self.parent().updateMachineMac(machineId, macAddres)

    def getMacRange(self):
        '''
        Returns de selected mac range
        '''
        return self.parent().getMacRange()

    def getBaseName(self):
        '''
        Returns the base name
        '''
        return self.baseName.value

    def getLenName(self):
        '''
        Returns the length of numbers part
        '''
        return int(self.lenName.value)

    def getDisplay(self):
        '''
        Returns the selected display type (for created machines, for administration
        '''
        return self.display.value

    def getConsoleConnection(self, machineId):
        return self.parent().getConsoleConnection(machineId)

    def desktopLogin(self, machineId, username, password, domain):
        return self.parent().desktopLogin(machineId, username, password, domain)
