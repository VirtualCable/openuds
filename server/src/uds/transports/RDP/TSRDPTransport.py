# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.util import connection
from uds.core.util.Cache import Cache
from web import generateHtmlForRdp, getHtmlComponent

import logging, random, string, time

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30

class TSRDPTransport(Transport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('RDP Transport (tunneled)')
    typeType = 'TSRDPTransport'
    typeDescription = _('RDP Transport for tunneled connection')
    iconFile = 'rdp.png' 
    needsJava = True  # If this transport needs java for rendering

    tunnelServer = gui.TextField(label=_('Tunnel server'), order = 1, tooltip = _('IP or Hostname of tunnel server send to client device ("public" ip) and port. (use HOST:PORT format)'))
    tunnelCheckServer = gui.TextField(label=_('Tunnel host check'), order = 2, tooltip = _('If not empty, this server will be used to check if service is running before assigning it to user. (use HOST:PORT format)'))
    
    useEmptyCreds = gui.CheckBoxField(label = _('Empty creds'), order = 3, tooltip = _('If checked, the credentials used to connect will be emtpy'))
    fixedName = gui.TextField(label=_('Username'), order = 4, tooltip = _('If not empty, this username will be always used as credential'))
    fixedPassword = gui.PasswordField(label=_('Password'), order = 5, tooltip = _('If not empty, this password will be always used as credential'))
    fixedDomain = gui.TextField(label=_('Domain'), order = 6, tooltip = _('If not empty, this domain will be always used as credential (used as DOMAIN\\user)'))
    allowSmartcards = gui.CheckBoxField(label = _('Allow Smartcards'), order = 7, tooltip = _('If checked, this transport will allow the use of smartcards'))
    allowPrinters = gui.CheckBoxField(label = _('Allow Printers'), order = 8, tooltip = _('If checked, this transport will allow the use of user printers'))
    allowDrives = gui.CheckBoxField(label = _('Allow Drives'), order = 9, tooltip = _('If checked, this transport will allow the use of user drives'))
    allowSerials = gui.CheckBoxField(label = _('Allow Serials'), order = 10, tooltip = _('If checked, this transport will allow the use of user serial ports'))
    
    def __init__(self, environment, values = None):
        super(TSRDPTransport, self).__init__(environment, values)
        if values != None:
            if values['tunnelServer'].find(':') == -1:
                raise Transport.ValidationException(_('Must use HOST:PORT in Tunnel Server Field'))
            self._tunnelServer = values['tunnelServer']
            self._tunnelCheckServer = values['tunnelCheckServer']
            self._useEmptyCreds = gui.strToBool(values['useEmptyCreds'])
            self._fixedName = values['fixedName']
            self._fixedPassword = values['fixedPassword']
            self._fixedDomain = values['fixedDomain']
            self._allowSmartcards = gui.strToBool(values['allowSmartcards'])
            self._allowPrinters = gui.strToBool(values['allowPrinters'])
            self._allowDrives = gui.strToBool(values['allowDrives'])
            self._allowSerials = gui.strToBool(values['allowSerials'])
            
        else:
            self._tunnelServer = ''
            self._tunnelCheckServer = ''
            self._useEmptyCreds = False
            self._fixedName = ''
            self._fixedPassword = ''
            self._fixedDomain = ''
            self._allowSmartcards = False
            self._allowPrinters = False
            self._allowDrives = False
            self._allowSerials = False
    
    def marshal(self):
        '''
        Serializes the transport data so we can store it in database
        '''
        return str.join( '\t', [ 'v1', gui.boolToStr(self._useEmptyCreds), gui.boolToStr(self._allowSmartcards), gui.boolToStr(self._allowPrinters), 
                                gui.boolToStr(self._allowDrives), gui.boolToStr(self._allowSerials),
                                self._fixedName, self._fixedPassword, self._fixedDomain, self._tunnelServer, self._tunnelCheckServer ] ) 
    
    def unmarshal(self, str):
        data = str.split('\t')
        if data[0] == 'v1':
            self._useEmptyCreds = gui.strToBool(data[1])
            self._allowSmartcards = gui.strToBool(data[2])
            self._allowPrinters = gui.strToBool(data[3])
            self._allowDrives = gui.strToBool(data[4])
            self._allowSerials = gui.strToBool(data[5])
            self._fixedName = data[6]
            self._fixedPassword = data[7]
            self._fixedDomain = data[8]
            self._tunnelServer = data[9]
            self._tunnelCheckServer = data[10]
        
    def valuesDict(self):
        return { 'allowSmartcards' : gui.boolToStr(self._allowSmartcards), 'allowPrinters' : gui.boolToStr(self._allowPrinters), 
                'allowDrives': gui.boolToStr(self._allowDrives), 'allowSerials': gui.boolToStr(self._allowSerials), 
                'fixedName' : self._fixedName, 'fixedPassword' : self._fixedPassword, 'fixedDomain' : self._fixedDomain, 
                'useEmptyCreds' : gui.boolToStr(self._useEmptyCreds), 'tunnelServer' : self._tunnelServer, 
                'tunnelCheckServer' : self._tunnelCheckServer }

    def isAvailableFor(self, ip):
        '''
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        '''
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache().get(ip)
        if ready is None:
            # Check again for readyness
            if connection.testServer(ip, '3389') == True:
                self.cache().put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            else:
                self.cache().put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'
    
    def renderForHtml(self, userService, idUserService, idTransport, ip, os, user, password):
        # We use helper to keep this clean
        username = user.getUsernameForAuth()
        prefs = user.prefs('rdp')
        
        proc = username.split('@')
        if len(proc) > 1:
            domain = proc[1]
        else:
            domain = ''
        username = proc[0]
        if self._fixedName is not '':
            username = self._fixedName
        if self._fixedPassword is not '':
            password = self._fixedPassword
        if self._fixedDomain is not '':
            domain = self._fixedDomain;
        if self._useEmptyCreds is True:
            username, password, domain = '','',''
        
        width, height = CommonPrefs.getWidthHeight(prefs)
        depth = CommonPrefs.getDepth(prefs)
        cache = Cache('pam')

        tunuser = ''.join(random.choice(string.letters + string.digits) for i in xrange(12)) + ("%f" % time.time()).split('.')[1]
        tunpass = ''.join(random.choice(string.letters + string.digits) for i in xrange(12))
        cache.put(tunuser, tunpass, 60*10) # Credential valid for ten minutes, and for 1 use only
        
        sshHost, sshPort = self._tunnelServer.split(':')
        
        logger.debug('Username generated: {0}, password: {1}'.format(tunuser, tunpass))
        tun = "{0} {1} {2} {3} {4} {5} {6}".format(tunuser, tunpass, sshHost, sshPort, ip, '3389', '9')
        ip = '127.0.0.1'
            
        # Extra data
        extra = { 'width': width, 'height' : height, 'depth' : depth, 
            'printers' : self._allowPrinters, 'smartcards' : self._allowSmartcards, 
            'drives' : self._allowDrives, 'serials' : self._allowSerials,
            'tun': tun, 'compression':True }
            
        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)
            
        return generateHtmlForRdp(self, idUserService, idTransport, os, ip, '-1', username, password, domain, extra)
        
    def getHtmlComponent(self, id, os, componentId):
        # We use helper to keep this clean
        return getHtmlComponent(self.__module__, componentId)
    