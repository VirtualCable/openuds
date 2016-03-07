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

from uds.core.ui import gui

import logging

__updated__ = '2016-03-07'

logger = logging.getLogger(__name__)


class LiveService(Service):
    '''
    Opennebula Live Service
    '''
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenNebula Live Images')
    # : Type used internally to identify this provider
    typeType = 'openNebulaLiveService'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenNebula live images bases service')
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
    template = gui.ChoiceField(label=_("Base Template"), order=1, tooltip=_('Service base template'), required=True)
    datastore = gui.ChoiceField(label=_("Datastore"), order=2, tooltip=_('Service clones datastore'), required=True)

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

    def initGui(self):
        '''
        Loads required values inside
        '''

        templates = self.parent().getTemplates()
        vals = []
        for t in templates:
            vals.append(gui.choiceItem(t[0], t[1]))

        # This is not the same case, values is not the "value" of the field, but
        # the list of values shown because this is a "ChoiceField"
        self.template.setValues(vals)

        datastores = self.parent().getDatastores()
        vals = []
        for d in datastores:
            vals.append(gui.choiceItem(d[0], d[1]))

        self.datastore.setValues(vals)

    def sanitizeVmName(self, name):
        return self.parent().sanitizeVmName(name)

    def makeTemplate(self, templateName):
        return self.parent().makeTemplate(self.template.value, templateName, self.datastore.value)

    def deployFromTemplate(self, name, templateId):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            displayType: 'vnc' or 'spice'. Display to use ad OpenNebula admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        '''
        logger.debug('Deploying from template {0} machine {1}'.format(templateId, name))
        # self.datastoreHasSpace()
        return self.parent().deployFromTemplate(name, templateId)

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
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().startMachine(machineId)

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().stopMachine(machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.parent().suspendMachine(machineId)

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

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
