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


import logging
import six

# Python bindings for OpenNebula
import oca

__updated__ = '2016-02-08'

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
    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=6, tooltip=_('Timeout in seconds of connection to OpenNebula'), required=True)
    macsRange = gui.TextField(length=36, label=_('Macs range'), defvalue='52:54:00:00:00:00-52:54:00:FF:FF:FF', order=7, rdonly=True,
                              tooltip=_('Range of valid macs for UDS managed machines'), required=True)

    # Own variables
    _api = None

    def initialize(self, values=None):
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.macsRange.value = validators.validateMacRange(self.macsRange.value)
            self.timeout.value = validators.validateTimeout(self.timeout.value, returnAsInteger=False)
            logger.debug('Endpoint: {}'.format(self.endPoint))

    @property
    def endpoint(self):
        return 'http{}://{}:{}/RPC2'.format('s' if self.ssl.isTrue() else '', self.host.value, self.port.value)


    @property
    def api(self):
        if self._api is None:
            self._api = oca.Client('{}:{}'.format(self.username.value, self.password.value), self.endpoint)

        return self._api

    def resetApi(self):
        self._api = None

    def sanitizeVmName(self, name):
        '''
        Ovirt only allows machine names with [a-zA-Z0-9_-]
        '''
        import re
        return re.sub("[^a-zA-Z0-9_-]", "_", name)

    def testConnection(self):
        '''
        Test that conection to OpenNebula server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        try:
            if self.api.version() < '4.1':
                return [False, 'OpenNebula version is not supported (required version 4.1 or newer)']
        except Exception as e:
            return [False, '{}'.format(e)]

        return [True, _('Opennebula test connection passed')]


    def getMachines(self, force=False):
        '''
        Obtains the list of machines inside OpenNebula.
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
        vmpool = oca.VirtualMachinePool(self.api)
        vmpool.info()

        return vmpool

    def getDatastores(self, datastoreType=0):
        '''
        0 seems to be images datastore
        '''
        datastores = oca.DatastorePool(self.api)
        datastores.info()

        for ds in datastores:
            if ds.type == datastoreType:
                yield ds

    def getTemplates(self, force=False):
        logger.debug('Api: {}'.format(self.api))
        templatesPool = oca.VmTemplatePool(self.api)
        templatesPool.info()

        for t in templatesPool:
            if t.name[:4] != 'UDSP':
                yield t

    def makeTemplate(self, fromTemplateId, name, toDataStore):
        '''
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            fromTemplateId: id of the base template
            name: Name of the machine (care, only ascii characters and no spaces!!!)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.

        Note:
            Maybe we need to also clone the hard disk?
        '''
        try:
            # First, we clone the themplate itself
            templateId = self.api.call('template.clone', int(fromTemplateId), name)

            # Now copy cloned images if possible
            try:
                imgs = oca.ImagePool(self.api)
                imgs.info()
                imgs = dict(((i.name, i.id) for i in imgs))

                info = self.api.call('template.info', templateId)
                template = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]
                logger.debug('XML: {}'.format(template.toxml()))

                counter = 0
                for dsk in template.getElementsByTagName('DISK'):
                    counter += 1
                    imgIds = dsk.getElementsByTagName('IMAGE_ID')
                    if len(imgIds) == 0:
                        fromId = False
                        node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                        imgName = node.data
                        # Locate
                        imgId = imgs[imgName]
                    else:
                        fromId = True
                        node = imgIds[0].childNodes[0]
                        imgId = node.data

                    logger.debug('Found {} for cloning'.format(imgId))

                    # Now clone the image
                    imgName = self.sanitizeVmName(name + ' DSK ' + six.text_type(counter))
                    newId = self.api.call('image.clone', int(imgId), imgName, int(toDataStore))
                    if fromId is True:
                        node.data = six.text_type(newId)
                    else:
                        node.data = imgName

                # Now update the clone
                self.api.call('template.update', templateId, template.toxml())
            except:
                logger.exception('Exception cloning image')

            return six.text_type(templateId)
        except Exception as e:
            logger.error('Creating template on OpenNebula: {}'.format(e))
            raise

    def removeTemplate(self, templateId):
        '''
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        '''
        try:
            # First, remove Images (wont be possible if there is any images already in use, but will try)
            # Now copy cloned images if possible
            try:
                imgs = oca.ImagePool(self.api)
                imgs.info()
                imgs = dict(((i.name, i.id) for i in imgs))

                info = self.api.call('template.info', int(templateId))
                template = minidom.parseString(info).getElementsByTagName('TEMPLATE')[0]
                logger.debug('XML: {}'.format(template.toxml()))

                counter = 0
                for dsk in template.getElementsByTagName('DISK'):
                    imgIds = dsk.getElementsByTagName('IMAGE_ID')
                    if len(imgIds) == 0:
                        node = dsk.getElementsByTagName('IMAGE')[0].childNodes[0]
                        imgId = imgs[node.data]
                    else:
                        node = imgIds[0].childNodes[0]
                        imgId = node.data

                    logger.debug('Found {} for cloning'.format(imgId))

                    # Now delete the image
                    self.api.call('image.delete', int(imgId))

            except:
                logger.exception('Exception cloning image')

            self.api.call('template.delete', int(templateId))
        except Exception as e:
            logger.error('Creating template on OpenNebula: {}'.format(e))

    def getMachineState(self, machineId):
        '''
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from OpenNebula server)

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

    def deployFromTemplate(self, name, comments, templateId, clusterId, displayType, memoryMB, guaranteedMB):
        '''
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad OpenNebula admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        '''
        return self.__getApi().deployFromTemplate(name, comments, templateId, clusterId, displayType, memoryMB, guaranteedMB)

    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().startMachine(machineId)

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().stopMachine(machineId)

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        return self.__getApi().suspendMachine(machineId)

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

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
        return Provider(env, data).testConnection()
