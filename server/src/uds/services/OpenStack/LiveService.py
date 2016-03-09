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

import six
import logging

__updated__ = '2016-03-09'

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
    region = gui.ChoiceField(label=_('Region'), order=1, tooltip=_('Service region'), required=True, rdonly=True)
    project = gui.ChoiceField(label=_('Project'), order=2,
        fills={
            'callbackName' : 'osFillResources',
            'function' : helpers.getResources,
            'parameters' : ['ov', 'ev', 'project', 'region']
            },
        tooltip=_('Project for this service'), required=True, rdonly=True
    )
    availabilityZone = gui.ChoiceField(label=_('Availability Zones'), order=3,
        fills={
            'callbackName' : 'osFillVolumees',
            'function' : helpers.getVolumes,
            'parameters' : ['ov', 'ev', 'project', 'region', 'availabilityZone']
            },
        tooltip=_('Service availability zones'), required=True, rdonly=True
    )
    volume = gui.ChoiceField(label=_('Volume'), order=4, tooltip=_('Base volume for service (restricted by availability zone)'), required=True)
    # volumeType = gui.ChoiceField(label=_('Volume Type'), order=5, tooltip=_('Volume type for service'), required=True)
    network = gui.ChoiceField(label=_('Network'), order=6, tooltip=_('Network to attach to this service'), required=True)
    flavor = gui.ChoiceField(label=_('Flavor'), order=7, tooltip=_('Flavor for service'), required=True)

    securityGroups = gui.MultiChoiceField(label=_('Security Groups'), order=8, tooltip=_('Service security groups'), required=True)

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

    ov = gui.HiddenField(value=None)
    ev = gui.HiddenField(value=None)  # We need to keep the env so we can instantiate the Provider

    def initialize(self, values):
        '''
        We check here form values to see if they are valid.

        Note that we check them through FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        '''
        if values is not None:
            length = int(self.lenName.value)
            if len(self.baseName.value) + length > 15:
                raise Service.ValidationException(_('The length of basename plus length must not be greater than 15'))
            if self.baseName.value.isdigit():
                raise Service.ValidationException(_('The machine name can\'t be only numbers'))

        # self.ov.value = self.parent().serialize()
        # self.ev.value = self.parent().env.key

        self._api = None


    def initGui(self):
        '''
        Loads required values inside
        '''
        api = self.parent().api()
        regions = [gui.choiceItem(r['id'], r['id']) for r in api.listRegions()]
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

    def getTemplate(self, snapshotId):
        '''
        Checks current state of a template (an snapshot)
        '''
        return self.api.getSnapshot(snapshotId)

    def deployFromTemplate(self, name, snapshotId):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            snapshotId: Id of the snapshot to deploy from

        Returns:
            Id of the machine being created form template
        '''
        logger.debug('Deploying from template {0} machine {1}'.format(snapshotId, name))
        # self.datastoreHasSpace()
        return self.api.createServerFromSnapshot(snapshotId=snapshotId,
                                          name=name,
                                          availabilityZone=self.availabilityZone.value,
                                          flavorId=self.flavor.value,
                                          networkId=self.network.value,
                                          securityGroupsIdsList=self.securityGroups.value)['id']

    def removeTemplate(self, templateId):
        '''
        invokes removeTemplate from parent provider
        '''
        self.api.deleteSnapshot(templateId)

    def getMachineState(self, machineId):
        '''
        Invokes getServer from openstack client

        Args:
            machineId: If of the machine to get state

        Returns:
            one of this values:
                ACTIVE. The server is active.
                BUILDING. The server has not finished the original build process.
                DELETED. The server is permanently deleted.
                ERROR. The server is in error.
                HARD_REBOOT. The server is hard rebooting. This is equivalent to pulling the power plug on a physical server, plugging it back in, and rebooting it.
                MIGRATING. The server is being migrated to a new host.
                PASSWORD. The password is being reset on the server.
                PAUSED. In a paused state, the state of the server is stored in RAM. A paused server continues to run in frozen state.
                REBOOT. The server is in a soft reboot state. A reboot command was passed to the operating system.
                REBUILD. The server is currently being rebuilt from an image.
                RESCUED. The server is in rescue mode. A rescue image is running with the original server image attached.
                RESIZED. Server is performing the differential copy of data that changed during its initial copy. Server is down for this stage.
                REVERT_RESIZE. The resize or migration of a server failed for some reason. The destination server is being cleaned up and the original source server is restarting.
                SOFT_DELETED. The server is marked as deleted but the disk images are still available to restore.
                STOPPED. The server is powered off and the disk image still persists.
                SUSPENDED. The server is suspended, either by request or necessity. This status appears for only the XenServer/XCP, KVM, and ESXi hypervisors. Administrative users can suspend an instance if it is infrequently used or to perform system maintenance. When you suspend an instance, its VM state is stored on disk, all memory is written to disk, and the virtual machine is stopped. Suspending an instance is similar to placing a device in hibernation; memory and vCPUs become available to create other instances.
                VERIFY_RESIZE. System is awaiting confirmation that the server is operational after a move or resize.
        '''
        return self.api.getServer(machineId)['status']

    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenStack.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.api.startServer(machineId)

    def stopMachine(self, machineId):
        '''
        Tries to stop a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.api.stopServer(machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to suspend a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.api.suspendServer(machineId)

    def resumeMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.api.suspendServer(machineId)


    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenStack

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.api.deleteServer(machineId)

    def getNetInfo(self, machineId):
        '''
        Gets the mac address of first nic of the machine
        '''
        net = self.api.getServer(machineId)['addresses']
        vals = six.next(six.itervalues(net))[0]  # Returns "any" mac address of any interface. We just need only one interface info
        return (vals['OS-EXT-IPS-MAC:mac_addr'], vals['addr'])

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
