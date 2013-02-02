# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core import osmanagers
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core.util.State import State
from uds.core.util import log

import logging

logger = logging.getLogger(__name__)


def scrambleMsg(data):
    '''
    Simple scrambler so password are not seen at source page
    '''
    res = []
    n = 0x32
    for c in data[::-1]:
        res.append( chr(ord(c) ^ n) )
        n = (n + ord(c)) & 0xFF
    return "".join(res).encode('hex')


class WindowsOsManager(osmanagers.OSManager):
    typeName = _('Windows Basic OS Manager')
    typeType = 'WindowsManager'
    typeDescription = _('Os Manager to control windows machines without domain. (Basically renames machine)')
    iconFile = 'wosmanager.png' 
    
    onLogout = gui.ChoiceField( label = _('On Logout'), order = 10, rdonly = False, tooltip = _('What to do when user logout from service'),
                     values = [ {'id' : 'keep', 'text' : _('Keep service assigned') }, 
                                {'id' : 'remove', 'text' : _('Remove service') }
                                ], defvalue = 'keep' )
                     
    
    @staticmethod
    def validateLen(len):
        try:
            len = int(len)
        except Exception:
            raise osmanagers.OSManager.ValidationException(_('Length must be numeric!!'))
        if len > 6 or len < 1:
            raise osmanagers.OSManager.ValidationException(_('Length must be betwen 1 and six'))
        return len
    
    def __init__(self,environment, values):
        super(WindowsOsManager, self).__init__(environment, values)
        if values is not None:
            self._onLogout = values['onLogout']
        else:
            self._onLogout = ''
            
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
            
    def doLog(self, service, data, origin = log.OSMANAGER):
        # Stores a log associated with this service
        try:
            
            msg, level = data.split('\t')
            log.doLog(service, level, msg, origin)
        except:
            log.doLog(service, log.ERROR, "do not understand {0}".format(data), origin)
        
        
    def process(self,service,msg, data):
        '''
        We understand this messages:
        * msg = info, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (old method)
        * msg = information, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (new method)
        * msg = logon, data = Username, Informs that the username has logged in inside the machine
        * msg = logoff, data = Username, Informs that the username has logged out of the machine 
        * msg = ready, data = None, Informs machine ready to be used
        '''
        logger.info("Invoked WindowsOsManager for {0} with params: {1},{2}".format(service, msg, data))
        # We get from storage the name for this service. If no name, we try to assign a new one
        ret = "ok"
        inUse = False
        notifyReady = False
        doRemove = False
        state = service.os_state
        if msg == "info":
            ret = self.infoVal(service)
            state = State.PREPARING
        elif msg == "information":
            ret = self.infoValue(service)
            state = State.PREPARING
        elif msg == "log":
            self.doLog(service, data, log.ACTOR)
        elif msg == "logon":
            si = service.getInstance()
            si.userLoggedIn(data)
            service.updateData(si)
            self.doLog(service, 'User {0} has logged IN\t{1}'.format(data, log.INFOSTR))
            # We get the service logged hostname & ip and returns this
            ip, hostname = service.getConnectionSource()
            ret = "{0}\t{1}".format(ip, hostname)
            inUse = True
        elif msg == "logoff":
            si = service.getInstance()
            si.userLoggedOut(data)
            service.updateData(si)
            self.doLog(service, 'User {0} has logged OUT\t{1}'.format(data, log.INFOSTR))
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
        return scrambleMsg(ret)
    
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
        
    def valuesDict(self):
        return { 'onLogout' : self._onLogout }
    