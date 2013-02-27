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
from uds.core import osmanagers
from uds.core.util.State import State

import logging
from uds.core.managers.UserServiceManager import UserServiceManager

logger = logging.getLogger(__name__)

class LinuxOsManager(osmanagers.OSManager):
    typeName = _('Linux OS Manager')
    typeType = 'LinuxManager'
    typeDescription = _('Os Manager to control linux virtual machines (basically renames machine and notify state)')
    iconFile = 'losmanager.png'
    
     

    onLogout = gui.ChoiceField( label = _('On Logout'), order = 10, rdonly = False, tooltip = _('What to do when user logout from service'),
                     values = [ {'id' : 'keep', 'text' : _('Keep service assigned') }, 
                                {'id' : 'remove', 'text' : _('Remove service') }
                                ], defvalue = 'keep' )

    def __setProcessUnusedMachines(self):
        self.processUnusedMachines = self._onLogout == 'remove'

    def __init__(self,environment, values):
        super(LinuxOsManager, self).__init__(environment, values)
        if values is not None:
            self._onLogout = values['onLogout']
        else:
            self._onLogout = ''

        self.__setProcessUnusedMachines()        
            
    def release(self, service):
        pass
            
    def getName(self, service):
        '''
        gets name from deployed
        '''
        return service.getName()
        
    def infoVal(self,service):
        return 'rename:' + self.getName(service)

    def infoValue(self,service):
        return 'rename\r' + self.getName(service)
    
    def notifyIp(self, uid, si, data):
        # Notifies IP to deployed
        pairs = data.split(',')
        for p in pairs:
            key, val = p.split('=')
            if key.lower() == uid.lower():
                si.setIp(val)
                break
        
    def process(self,service,msg, data):
        '''
        We understand this messages:
        * msg = info, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class), old method
        * msg = information, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class), new method
        * msg = logon, data = Username, Informs that the username has logged in inside the machine
        * msg = logoff, data = Username, Informs that the username has logged out of the machine 
        * msg = ready, data = None, Informs machine ready to be used
        '''
        logger.info("Invoked LinuxOsManager for {0} with params: {1},{2}".format(service, msg, data))
        # We get from storage the name for this service. If no name, we try to assign a new one
        ret = "ok"
        inUse = False
        notifyReady = False
        doRemove = False
        state = service.os_state
        
        # Old "info" state, will be removed in a near future
        if msg == "info":
            ret = self.infoVal(service)
            state = State.PREPARING
        elif msg == "information":
            ret = self.infoValue(service)
            state = State.PREPARING
        elif msg == "login":
            si = service.getInstance()
            si.userLoggedIn(data)
            service.updateData(si)
            inUse = True
        elif msg == "logout":
            si = service.getInstance()
            si.userLoggedOut(data)
            service.updateData(si)
            if self._onLogout == 'remove':
                doRemove = True
        elif msg == "ip":
            # This ocurss on main loop inside machine, so service is usable
            state = State.USABLE
            si = service.getInstance()
            self.notifyIp(service.unique_id, si, data)
            service.updateData(si)
        elif msg == "ready":
            state = State.USABLE
            si = service.getInstance()
            notifyReady = True
            self.notifyIp(service.unique_id, si, data)
            service.updateData(si)
        service.setInUse(inUse)
        service.setOsState(state)
        # If notifyReady is not true, save state, let UserServiceManager do it for us else
        if doRemove is True:
            service.remove()
        else:
            if notifyReady is False:
                service.save()
            else:
                UserServiceManager.manager().notifyReadyFromOsManager(service, '')
        logger.debug('Returning {0}'.format(ret))
        return ret
    
    def processUnused(self, userService):
        '''
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        '''
        if self._onLogout == 'remove':
            userService.remove()
    
    
    def checkState(self,service):
        logger.debug('Checking state for service {0}'.format(service))
        return State.RUNNING

    def marshal(self):
        '''
        Serializes the os manager data so we can store it in database
        '''
        return str.join( '\t', [ 'v1', self._onLogout ] ) 
    
    def unmarshal(self, s):
        data = s.split('\t')
        if data[0] == 'v1':
            self._onLogout = data[1]
        self.__setProcessUnusedMachines()        
        
    def valuesDict(self):
        return { 'onLogout' : self._onLogout }
