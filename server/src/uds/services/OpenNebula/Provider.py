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
from defusedxml import minidom

from .LiveService import LiveService
from . import on


import logging
import six

# Python bindings for OpenNebula
# import oca

__updated__ = '2016-11-23'

logger = logging.getLogger(__name__)

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
    offers = [LiveService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenNebula Platform Provider')
    # : Type used internally to identify this provider
    typeType = 'openNebulaPlatform'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenNebula platform service provider')
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
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('OpenNebula Host'), required=True)
    port = gui.NumericField(length=5, label=_('Port'), defvalue='2633', order=2, tooltip=_('OpenNebula Port (default is 2633 for non ssl connection)'), required=True)
    ssl = gui.CheckBoxField(label=_('Use SSL'), order=3, tooltip=_('If checked, the connection will be forced to be ssl (will not work if server is not providing ssl)'))
    username = gui.TextField(length=32, label=_('Username'), order=4, tooltip=_('User with valid privileges on OpenNebula'), required=True, defvalue='oneadmin')
    password = gui.PasswordField(lenth=32, label=_('Password'), order=5, tooltip=_('Password of the user of OpenNebula'), required=True)

    maxPreparingServices = gui.NumericField(length=3, label=_('Creation concurrency'), defvalue='10', minValue=1, maxValue=65536, order=50, tooltip=_('Maximum number of concurrently creating VMs'), required=True, tab=gui.ADVANCED_TAB)
    maxRemovingServices = gui.NumericField(length=3, label=_('Removal concurrency'), defvalue='5', minValue=1, maxValue=65536, order=51, tooltip=_('Maximum number of concurrently removing VMs'), required=True, tab=gui.ADVANCED_TAB)

    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=90, tooltip=_('Timeout in seconds of connection to OpenNebula'), required=True, tab=gui.ADVANCED_TAB)

    # Own variables
    _api = None

    def initialize(self, values=None):
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.timeout.value = validators.validateTimeout(self.timeout.value, returnAsInteger=False)
            logger.debug('Endpoint: {}'.format(self.endpoint))

    @property
    def endpoint(self):
        return 'http{}://{}:{}/RPC2'.format('s' if self.ssl.isTrue() else '', self.host.value, self.port.value)


    @property
    def api(self):
        if self._api is None:
            self._api = on.OpenNebulaClient(self.username.value, self.password.value, self.endpoint)

        logger.debug('Api: {}'.format(self._api))
        return self._api

    def resetApi(self):
        self._api = None

    def sanitizeVmName(self, name):
        return on.sanitizeName(name)

    def testConnection(self):
        '''
        Test that conection to OpenNebula server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        try:
            if self.api.version[0] < '4':
                return [False, 'OpenNebula version is not supported (required version 4.1 or newer)']
        except Exception as e:
            return [False, '{}'.format(e)]

        return [True, _('Opennebula test connection passed')]

    def getDatastores(self, datastoreType=0):
        return on.storage.enumerateDatastores(self.api, datastoreType)

    def getTemplates(self, force=False):
        return on.template.getTemplates(self.api, force)

    def makeTemplate(self, fromTemplateId, name, toDataStore):
        return on.template.create(self.api, fromTemplateId, name, toDataStore)

    def checkTemplatePublished(self, templateId):
        return on.template.checkPublished(self.api, templateId)

    def removeTemplate(self, templateId):
        return on.template.remove(self.api, templateId)

    def deployFromTemplate(self, name, templateId):
        return on.template.deployFrom(self.api, templateId, name)

    def getMachineState(self, machineId):
        '''
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from OpenNebula server)

        Args:
            machineId: Id of the machine to get state

        Returns:
            one of the on.VmState Values
        '''
        return on.vm.getMachineState(self.api, machineId)


    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.startMachine(self.api, machineId)

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.stopMachine(self.api, machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.suspendMachine(self.api, machineId)

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.removeMachine(self.api, machineId)

    def getNetInfo(self, machineId, networkId=None):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return on.vm.getNetInfo(self.api, machineId, networkId)

    def getConsoleConnection(self, machineId):
        display = on.vm.getDisplayConnection(self.api, machineId)

        return {
            'type': display['type'],
            'address': display['host'],
            'port': display['port'],
            'secure_port':-1,
            'monitors': 1,
            'cert_subject': '',
            'ticket': {
                'value': '',
                'expiry': ''
            }
        }


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
        return Provider(env, data).testConnection()
