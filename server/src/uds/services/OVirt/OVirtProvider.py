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
Created on Jun 22, 2012

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators

from .OVirtLinkedService import OVirtLinkedService

from .client import oVirtClient

import logging

__updated__ = '2016-06-04'

logger = logging.getLogger(__name__)

CACHE_TIME_FOR_SERVER = 1800


class Provider(ServiceProvider):
    '''
    This class represents the sample services provider

    In this class we provide:
       * The Provider functionality
       * The basic configuration parameters for the provider
       * The form fields needed by administrators to configure this provider

       :note: At class level, the translation must be simply marked as so
       using ugettext_noop. This is so cause we will translate the string when
       sent to the administration client.

    For this class to get visible at administration client as a provider type,
    we MUST register it at package __init__.

    '''
    # : What kind of services we offer, this are classes inherited from Service
    offers = [OVirtLinkedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('oVirt/RHEV Platform Provider')
    # : Type used internally to identify this provider
    typeType = 'oVirtPlatform'
    # : Description shown at administration interface for this provider
    typeDescription = _('oVirt platform service provider')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    iconFile = 'provider.png'

    # now comes the form fields
    # There is always two fields that are requested to the admin, that are:
    # Service Name, that is a name that the admin uses to name this provider
    # Description, that is a short description that the admin gives to this provider
    # Now we are going to add a few fields that we need to use this provider
    # Remember that these are "dummy" fields, that in fact are not required
    # but used for sample purposes
    # If we don't indicate an order, the output order of fields will be
    # "random"
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('oVirt Server IP or Hostname'), required=True)
    username = gui.TextField(length=32, label=_('Username'), order=3, tooltip=_('User with valid privileges on oVirt, (use "user@domain" form)'), required=True, defvalue='admin@internal')
    password = gui.PasswordField(lenth=32, label=_('Password'), order=4, tooltip=_('Password of the user of oVirt'), required=True)

    maxPreparingServices = gui.NumericField(length=3, label=_('Creation concurrency'), defvalue='10', minValue=1, maxValue=65536, order=50, tooltip=_('Maximum number of concurrently creating VMs'), required=True, tab=gui.ADVANCED_TAB)
    maxRemovingServices = gui.NumericField(length=3, label=_('Removal concurrency'), defvalue='5', minValue=1, maxValue=65536, order=51, tooltip=_('Maximum number of concurrently removing VMs'), required=True, tab=gui.ADVANCED_TAB)

    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=90, tooltip=_('Timeout in seconds of connection to oVirt'), required=True, tab=gui.ADVANCED_TAB)
    macsRange = gui.TextField(length=36, label=_('Macs range'), defvalue='52:54:00:00:00:00-52:54:00:FF:FF:FF', order=91, rdonly=True,
                              tooltip=_('Range of valid macs for UDS managed machines'), required=True, tab=gui.ADVANCED_TAB)

    # Own variables
    _api = None

    # oVirt engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def __getApi(self):
        '''
        Returns the connection API object for oVirt (using ovirtsdk)
        '''
        if self._api is None:
            self._api = oVirtClient.Client(self.host.value, self.username.value, self.password.value, self.timeout.value, self.cache)
        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values=None):
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.macsRange.value = validators.validateMacRange(self.macsRange.value)
            self.timeout.value = validators.validateTimeout(self.timeout.value, returnAsInteger=False)
            logger.debug(self.host.value)

    def testConnection(self):
        '''
        Test that conection to oVirt server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        return self.__getApi().test()

    def testValidVersion(self):
        '''
        Checks that this version of ovirt if "fully functional" and does not needs "patchs'
        '''
        return self.__getApi().isFullyFunctionalVersion()

    def getMachines(self, force=False):
        '''
        Obtains the list of machines inside oVirt.
        Machines starting with UDS are filtered out

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'cluster_id'
        '''

        return self.__getApi().getVms(force)

    def getClusters(self, force=False):
        '''
        Obtains the list of clusters inside oVirt.

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            Filters out clusters not attached to any datacenter
            An array of dictionaries, containing:
                'name'
                'id'
                'datacenter_id'
        '''

        return self.__getApi().getClusters(force)

    def getClusterInfo(self, clusterId, force=False):
        '''
        Obtains the cluster info

        Args:
            datacenterId: Id of the cluster to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'datacenter_id'
        '''
        return self.__getApi().getClusterInfo(clusterId, force)

    def getDatacenterInfo(self, datacenterId, force=False):
        '''
        Obtains the datacenter info

        Args:
            datacenterId: Id of the datacenter to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'storage_type' -> ('isisi', 'nfs', ....)
                'storage_format' -> ('v1', v2')
                'description'
                'storage' -> array of dictionaries, with:
                   'id' -> Storage id
                   'name' -> Storage name
                   'type' -> Storage type ('data', 'iso')
                   'available' -> Space available, in bytes
                   'used' -> Space used, in bytes
                   'active' -> True or False

        '''
        return self.__getApi().getDatacenterInfo(datacenterId, force)

    def getStorageInfo(self, storageId, force=False):
        '''
        Obtains the storage info

        Args:
            storageId: Id of the storage to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
               'id' -> Storage id
               'name' -> Storage name
               'type' -> Storage type ('data', 'iso')
               'available' -> Space available, in bytes
               'used' -> Space used, in bytes
               # 'active' -> True or False --> This is not provided by api?? (api.storagedomains.get)

        '''
        return self.__getApi().getStorageInfo(storageId, force)

    def makeTemplate(self, name, comments, machineId, clusterId, storageId, displayType):
        '''
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            name: Name of the machine (care, only ascii characters and no spaces!!!)
            machineId: id of the machine to be published
            clusterId: id of the cluster that will hold the machine
            storageId: id of the storage tuat will contain the publication AND linked clones
            displayType: type of display (for oVirt admin interface only)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.
        '''
        return self.__getApi().makeTemplate(name, comments, machineId, clusterId, storageId, displayType)

    def getTemplateState(self, templateId):
        '''
        Returns current template state.

        Returned values could be:
            ok
            locked
            removed

        (don't know if ovirt returns something more right now, will test what happens when template can't be published)
        '''
        return self.__getApi().getTemplateState(templateId)

    def getMachineState(self, machineId):
        '''
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from oVirt server)

        Args:
            machineId: Id of the machine to get state

        Returns:
            one of this values:
             unassigned, down, up, powering_up, powered_down,
             paused, migrating_from, migrating_to, unknown, not_responding,
             wait_for_launch, reboot_in_progress, saving_state, restoring_state,
             suspended, image_illegal, image_locked or powering_down
             Also can return'unknown' if Machine is not known
        '''
        return self.__getApi().getMachineState(machineId)

    def removeTemplate(self, templateId):
        '''
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        '''
        return self.__getApi().removeTemplate(templateId)

    def deployFromTemplate(self, name, comments, templateId, clusterId, displayType, usbType, memoryMB, guaranteedMB):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad oVirt admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        '''
        return self.__getApi().deployFromTemplate(name, comments, templateId, clusterId, displayType, usbType, memoryMB, guaranteedMB)

    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().startMachine(machineId)

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().stopMachine(machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().suspendMachine(machineId)

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().removeMachine(machineId)

    def updateMachineMac(self, machineId, macAddres):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return self.__getApi().updateMachineMac(machineId, macAddres)

    def getMacRange(self):
        return self.macsRange.value

    def getConsoleConnection(self, machineId):
        return self.__getApi().getConsoleConnection(machineId)

    def desktopLogin(self, machineId, username, password, domain):
        '''
        '''
        return self.__getApi().desktopLogin(machineId, username, password, domain)

    @staticmethod
    def test(env, data):
        '''
        Test ovirt Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..

        '''
        # try:
        #    # We instantiate the provider, but this may fail...
        #    instance = Provider(env, data)
        #    logger.debug('Methuselah has {0} years and is {1} :-)'
        #                 .format(instance.methAge.value, instance.methAlive.value))
        # except ServiceProvider.ValidationException as e:
        #    # If we say that meth is alive, instantiation will
        #    return [False, str(e)]
        # except Exception as e:
        #    logger.exception("Exception caugth!!!")
        #    return [False, str(e)]
        # return [True, _('Nothing tested, but all went fine..')]
        ov = Provider(env, data)
        if ov.testConnection() is True:
            return ov.testValidVersion()

        return [False, _("Connection failed. Check connection params")]





