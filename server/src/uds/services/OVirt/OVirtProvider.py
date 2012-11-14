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

from django.utils.translation import ugettext_noop as translatable, ugettext as _
from uds.core.services import ServiceProvider
from OVirtLinkedService import OVirtLinkedService
from uds.core.ui import gui

from client import oVirtClient

import logging

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
    #: What kind of services we offer, this are classes inherited from Service
    offers = [OVirtLinkedService]
    #: Name to show the administrator. This string will be translated BEFORE
    #: sending it to administration interface, so don't forget to
    #: mark it as translatable (using ugettext_noop)
    typeName = translatable('oVirt Platform Provider') 
    #: Type used internally to identify this provider
    typeType = 'oVirtPlatform'
    #: Description shown at administration interface for this provider
    typeDescription = translatable('oVirt platform service provider')
    #: Icon file used as icon for this provider. This string will be translated 
    #: BEFORE sending it to administration interface, so don't forget to
    #: mark it as translatable (using ugettext_noop)
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
    host = gui.TextField(length=64, label = _('Host'), order = 1, tooltip = _('oVirt Server IP or Hostname'), required = True)
    username = gui.TextField(length=32, label = _('Username'), order = 3, tooltip = _('User with valid privileges on oVirt, (use "user@domain" form'), required = True, defvalue='admin@internal')
    password = gui.PasswordField(lenth=32, label = _('Password'), order = 4, tooltip = _('Password of the user of oVirt'), required = True)
    timeout = gui.NumericField(length=3, label = _('Timeout'), defvalue = '10', order = 5, tooltip = _('Timeout in seconds of connection to VC'), required = True)
    macsRange = gui.TextField(length=36, label = _('Macs range'), defvalue = '52:54:00:00:00:00-52:54:00:FF:FF:FF', order = 6, rdonly = True,  
                              tooltip = _('Range of valids macs for created machines'), required = True)

    
    
    # oVirt engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def __getApi(self):
        '''
        Returns the connection API object for oVirt (using ovirtsdk)
        '''
        if self._api is None:
            self._api =  oVirtClient.Client(self.host.value, self.username.value, self.password.value, self.timeout.value, self.cache())
        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values = None):
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable                
        self._api = None

    def testConnection(self):
        api = self.__getApi()
        return api.test()
    
    
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
        #try:
        #    # We instantiate the provider, but this may fail...
        #    instance = Provider(env, data)
        #    logger.debug('Methuselah has {0} years and is {1} :-)'
        #                 .format(instance.methAge.value, instance.methAlive.value))
        #except ServiceProvider.ValidationException as e:
        #    # If we say that meth is alive, instantiation will 
        #    return [False, str(e)]
        #except Exception as e:
        #    logger.exception("Exception caugth!!!")
        #    return [False, str(e)]
        #return [True, _('Nothing tested, but all went fine..')]
        ov = Provider(env, data)
        if ov.testConnection() is True:
            return [True, _('Connection test successful')]
        return [False, _("Connection failed. Check connection params")]
    


    

