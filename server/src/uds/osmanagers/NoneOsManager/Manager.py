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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core.osmanagers.BaseOsManager import BaseOSManager, State

import logging

logger = logging.getLogger(__name__)

class NoneOSManager(BaseOSManager):
    typeName = _('None OS Manager')
    typeType = 'NoneOSManager'
    typeDescription = _('Os Manager with no actions')
    iconFile = 'osmanager.png' 
    
    def __init__(self,environment, values):
        super(NoneOSManager, self).__init__(environment, values)
        
    def process(self,service,msg, data):
        logger.info("Invoked NoneOsManager for {0} with params: {1}, {2}".format(service, msg, data))
        return "noneos"
    
    def checkState(self,service):
        logger.debug('Checking state for service {0}'.format(service))
        return State.FINISHED

    def marshal(self):
        '''
        Serializes the os manager data so we can store it in database
        '''
        return str.join( '\t', [ 'v1' ] ) 
    
    def unmarshal(self, str):
        data = str.split('\t')
        if data[0] == 'v1':
            pass
        
    def valuesDict(self):
        return {}
    