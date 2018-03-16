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
Created on Apr 8, 2014

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.util.State import State
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators

from xen_client import XenServer
from xen_client import XenFailure, XenFault

from XenLinkedService import XenLinkedService

import six
import logging

logger = logging.getLogger(__name__)

__updated__ = '2018-03-16'

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
    offers = [XenLinkedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('Xenserver Platform Provider')
    # : Type used internally to identify this provider
    typeType = 'XenPlatform'
    # : Description shown at administration interface for this provider
    typeDescription = _('XenServer platform service provider')
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
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('XenServer Server IP or Hostname'), required=True)
    username = gui.TextField(length=32, label=_('Username'), order=2, tooltip=_('User with valid privileges on XenServer'), required=True, defvalue='root')
    password = gui.PasswordField(lenth=32, label=_('Password'), order=3, tooltip=_('Password of the user of XenServer'), required=True)

    maxPreparingServices = gui.NumericField(length=3, label=_('Creation concurrency'), defvalue='10', minValue=1, maxValue=65536, order=50, tooltip=_('Maximum number of concurrently creating VMs'), required=True, tab=gui.ADVANCED_TAB)
    maxRemovingServices = gui.NumericField(length=3, label=_('Removal concurrency'), defvalue='5', minValue=1, maxValue=65536, order=51, tooltip=_('Maximum number of concurrently removing VMs'), required=True, tab=gui.ADVANCED_TAB)

    macsRange = gui.TextField(length=36, label=_('Macs range'), defvalue='02:46:00:00:00:00-02:46:00:FF:FF:FF', order=90, rdonly=True,
                              tooltip=_('Range of valid macs for created machines'), required=True, tab=gui.ADVANCED_TAB)
    verifySSL = gui.CheckBoxField(label=_('Verify Certificate'), order=91,
                                  tooltip=_('If selected, certificate will be checked against system valid certificate providers'), required=True, tab=gui.ADVANCED_TAB)

    # XenServer engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def __getApi(self, force=False):
        '''
        Returns the connection API object for XenServer (using XenServersdk)
        '''
        logger.debug('API verifySSL: {} {}'.format(self.verifySSL.value, self.verifySSL.isTrue()))
        if self._api is None or force:
            self._api = XenServer(self.host.value, '443', self.username.value, self.password.value, True, self.verifySSL.isTrue())
        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values=None):
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

    def testConnection(self):
        '''
        Test that conection to XenServer server is fine

        Returns

            True if all went fine, false if id didn't
        '''
        self.__getApi().test()

    def checkTaskFinished(self, task):
        '''
        Checks a task state.
        Returns None if task is Finished
        Returns a number indicating % of completion if running
        Raises an exception with status else ('cancelled', 'unknown', 'failure')
        '''
        if task is None or task == '':
            return (True, '')
        ts = self.__getApi().getTaskInfo(task)
        logger.debug('Task status: {0}'.format(ts))
        if ts['status'] == 'running':
            return (False, ts['progress'])
        if ts['status'] == 'success':
            return (True, ts['result'])

        # Any other state, raises an exception
        raise Exception(six.text_type(ts['result']))  # Should be error message

    def getMachines(self, force=False):
        '''
        Obtains the list of machines inside XenServer.
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

        for m in self.__getApi().getVMs():
            if m['name'][:3] == 'UDS':
                continue
            yield m

    def getStorages(self, force=False):
        '''
        Obtains the list of storages inside XenServer.

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'size'
                'used'
        '''
        return self.__getApi().getSRs()

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
        return self.__getApi().getSRInfo(storageId)

    def getNetworks(self, force=False):
        return self.__getApi().getNetworks()

    def cloneForTemplate(self, name, comments, machineId, sr):
        task = self.__getApi().cloneVM(machineId, name, sr)
        logger.debug('Task for cloneForTemplate: {0}'.format(task))
        return task

    def convertToTemplate(self, machineId, shadowMultiplier=4):
        '''
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            name: Name of the machine (care, only ascii characters and no spaces!!!)
            machineId: id of the machine to be published
            clusterId: id of the cluster that will hold the machine
            storageId: id of the storage tuat will contain the publication AND linked clones
            displayType: type of display (for XenServer admin interface only)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.
        '''
        self.__getApi().convertToTemplate(machineId, shadowMultiplier)

    def getMachineState(self, machineId):
        '''
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from XenServer server)

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

        return State.INACTIVE

    def removeTemplate(self, templateId):
        '''
        Removes a template from XenServer server

        Returns nothing, and raises an Exception if it fails
        '''
        return self.__getApi().removeTemplate(templateId)

    def startDeployFromTemplate(self, name, comments, templateId):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad XenServer admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        '''
        return self.__getApi().cloneTemplate(templateId, name)

    def getVMPowerState(self, machineId):
        '''
        Returns current machine power state
        '''
        return self.__getApi().getVMPowerState(machineId)

    def startVM(self, machineId, async=True):
        '''
        Tries to start a machine. No check is done, it is simply requested to XenServer.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().startVM(machineId, async)

    def stopVM(self, machineId, async=True):
        '''
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().stopVM(machineId, async)

    def resetVM(self, machineId, async=True):
        '''
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().resetVM(machineId, async)

    def canSuspendVM(self, machineId):
        '''
        The machine can be suspended only when "suspend" is in their operations list (mush have xentools installed)

        Args:
            machineId: Id of the machine

        Returns:
            True if the machien can be suspended
        '''
        return self.__getApi().canSuspendVM(machineId)

    def suspendVM(self, machineId, async=True):
        '''
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().suspendVM(machineId, async)

    def resumeVM(self, machineId, async=True):
        '''
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().resumeVM(machineId, async)

    def removeVM(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().removeVM(machineId)

    def configureVM(self, machineId, netId, mac, memory):
        self.__getApi().configureVM(machineId, mac={'network': netId, 'mac': mac}, memory=memory)

    def provisionVM(self, machineId, async):
        return self.__getApi().provisionVM(machineId, async=async)

    def getMacRange(self):
        return self.macsRange.value

    @staticmethod
    def test(env, data):
        '''
        Test XenServer Connectivity

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
        xe = Provider(env, data)
        try:
            xe.testConnection()
            return [True, _('Connection test successful')]
        except Exception as e:
            return [False, _("Connection failed: {0}").format(unicode(e))]
