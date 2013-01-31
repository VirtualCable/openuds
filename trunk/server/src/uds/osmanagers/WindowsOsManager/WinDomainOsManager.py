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
from uds.core.managers.CryptoManager import CryptoManager
from uds.core import osmanagers
from WindowsOsManager import WindowsOsManager, scrambleMsg

import logging

logger = logging.getLogger(__name__)

class WinDomainOsManager(WindowsOsManager):
    typeName = _('Windows Domain OS Manager')
    typeType = 'WinDomainManager'
    typeDescription = _('Os Manager to control windows machines with domain. (Basically renames machine)')
    iconFile = 'wosmanager.png' 
    
    # Apart form data from windows os manager, we need also domain and credentials
    domain = gui.TextField(length=64, label = _('Domain'), order = 1, tooltip = _('Domain to join machines to (better use dns form of domain)'), required = True)
    account = gui.TextField(length=64, label = _('Account'), order = 2, tooltip = _('Account with rights to add machines to domain'), required = True)
    password = gui.PasswordField(length=64, label = _('Password'), order = 3, tooltip = _('Password of the account'), required = True)
    ou = gui.TextField(length=64, label = _('OU'), order = 4, tooltip = _('Organizational unit where to add machines in domain (check it before using it)'))
    # Inherits base "onLogout"
    onLogout = WindowsOsManager.onLogout
    
    def __init__(self,environment, values):
        super(WinDomainOsManager, self).__init__(environment, values)
        if values != None:
            if values['domain'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide a domain!!!'))
            if values['account'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide an account to add machines to domain!!!'))
            if values['password'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide a password for the account!!!'))
            self._domain = values['domain']
            self._ou = values['ou']
            self._account = values['account']
            self._password = values['password']
        else:
            self._domain = ""
            self._ou = ""
            self._account = ""
            self._password = ""
    
    def release(self, service):
        super(WinDomainOsManager,self).release(service)
        # TODO: remove machine from active directory os, under ou or default location if not specified
        
    def infoVal(self, service):
        return 'domain:{0}\t{1}\t{2}\t{3}\t{4}'.format( self.getName(service), self._domain, self._ou, self._account, self._password)

    def infoValue(self, service):
        return 'domain\r{0}\t{1}\t{2}\t{3}\t{4}'.format( self.getName(service), self._domain, self._ou, self._account, self._password)
        
    def marshal(self):
        base = super(WinDomainOsManager,self).marshal()
        '''
        Serializes the os manager data so we can store it in database
        '''
        return str.join( '\t', [ 'v1', self._domain, self._ou, self._account, CryptoManager.manager().encrypt(self._password), base.encode('hex') ] ) 
    
    def unmarshal(self, s):
        data = s.split('\t')
        if data[0] == 'v1':
            self._domain = data[1]
            self._ou = data[2]
            self._account = data[3]
            self._password = CryptoManager.manager().decrypt(data[4])
            super(WinDomainOsManager, self).unmarshal(data[5].decode('hex'))
        
    def valuesDict(self):
        dict = super(WinDomainOsManager,self).valuesDict()
        dict['domain'] = self._domain
        dict['ou'] = self._ou
        dict['account'] = self._account
        dict['password'] = self._password
        return dict
    
