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
from .LivePublication import LivePublication
from .LiveDeployment import LiveDeployment
from . import helpers

from uds.core.ui import gui


import logging

__updated__ = '2016-03-04'

logger = logging.getLogger(__name__)


class LiveService(Service):
    '''
    OpenStack Live Service
    '''
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenStack Live Volume')
    # : Type used internally to identify this provider
    typeType = 'openStackLiveService'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenStack live images bases service')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    iconFile = 'provider.png'

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
    cacheTooltip = _('Number of desired machines to keep running waiting for an user')

    usesCache_L2 = True  # L2 Cache are running machines in suspended state
    cacheTooltip_L2 = _('Number of desired machines to keep suspended waiting for use')
    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = True
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = LivePublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = LiveDeployment

    allowedProtocols = protocols.GENERIC + (protocols.SPICE,)
    servicesTypeProvided = (serviceTypes.VDI,)

    # Now the form part
    region = gui.ChoiceField(label=_("Region"), order=1, tooltip=_('Service region'), required=True)
    project = gui.ChoiceField(label=_("Project"), order=2,
        fills={
            'callbackName' : 'osFillResources',
            'function' : helpers.getResources,
            'parameters' : ['ov', 'ev', 'project', 'region']
            },
        tooltip=_('Project for this service'), required=True
    )
    availabilityZone = gui.ChoiceField(label=_("Availability Zones"), order=3, tooltip=_('Service availability zones'), required=True)
    volume = gui.ChoiceField(label=_("Volume"), order=4, tooltip=_('Base volume for service'), required=True)
    # volumeType = gui.ChoiceField(label=_("Volume Type"), order=5, tooltip=_('Volume type for service'), required=True)
    networks = gui.MultiChoiceField(label=_("Networks"), order=6, tooltip=_('Networks to attach to this service'), required=True)
    flavor = gui.ChoiceField(label=_("Flavor"), order=7, tooltip=_('Flavor for service'), required=True)

    securityGroups = gui.MultiChoiceField(label=_("Security Groups"), order=8, tooltip=_('Service security groups'), required=True)

    baseName = gui.TextField(
        label=_('Machine Names'),
        rdonly=False,
        order=9,
        tooltip=_('Base name for clones from this machine'),
        required=True
    )

    lenName = gui.NumericField(
        length=1,
        label=_('Name Length'),
        defvalue=5,
        order=10,
        tooltip=_('Size of numeric part for the names of these machines (between 3 and 6)'),
        required=True
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

        self.ov.value = self.parent().serialize()
        self.ev.value = self.parent().env.key

        self._api = None


    def initGui(self):
        '''
        Loads required values inside
        '''
        api = self.parent().api()
        regions = [gui.choiceItem(r, r) for r in api.listRegions()]
        self.region.setValues(regions)

        tenants = [gui.choiceItem(t['id'], t['name']) for t in api.listProjects()]
        self.project.setValues(tenants)

        # So we can instantiate parent to get API
        logger.debug(self.parent().serialize())
        self.ov.setDefValue(self.parent().serialize())
        self.ev.setDefValue(self.parent().env.key)

    @property
    def api(self):
        if self._api is None:
            self._api = self.parent().api(projectId=self.project.value, region=self.region.value)

        return self._api

    def sanitizeVmName(self, name):
        return self.parent().sanitizeVmName(name)

    def makeTemplate(self, templateName, description=None):
        # First, ensures that volume has not any running instances
        if self.api.getVolume(self.volume.value)['status'] != 'available':
            raise Exception('The Volume is in use right now. Ensure that there is no machine running before publishing')

        description = 'UDS Template snapshot' if description is None else description
        return self.api.createVolumeSnapshot(self.volume.value, templateName, description)

    def deployFromTemplate(self, name, snapshotId):
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
        logger.debug('Deploying from template {0} machine {1}'.format(snapshotId, name))
        # self.datastoreHasSpace()
        # self.api.

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

    def getNetInfo(self, machineId, networkId=None):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return self.parent().getNetInfo(machineId, networkId=None)

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
