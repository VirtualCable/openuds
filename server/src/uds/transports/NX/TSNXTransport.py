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
Created on Jul 29, 2011

@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.util.Cache import Cache
from uds.core.util import connection
from web import generateHtmlForNX, getHtmlComponent

import logging, random, string, time

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30

class TSNXTransport(Transport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('NX Transport (tunneled)')
    typeType = 'TSNXTransport'
    typeDescription = _('NX Transport for tunneled connection')
    iconFile = 'nx.png' 
    needsJava = True  # If this transport needs java for rendering
    supportedOss = ['Windows', 'Macintosh', 'Linux']

    tunnelServer = gui.TextField(label=_('Tunnel server'), order = 1, tooltip = _('IP or Hostname of tunnel server send to client device ("public" ip) and port. (use HOST:PORT format)'))
    tunnelCheckServer = gui.TextField(label=_('Tunnel host check'), order = 2, tooltip = _('If not empty, this server will be used to check if service is running before assigning it to user. (use HOST:PORT format)'))

    useEmptyCreds = gui.CheckBoxField(label = _('Empty creds'), order = 3, tooltip = _('If checked, the credentials used to connect will be emtpy'))
    fixedName = gui.TextField(label=_('Username'), order = 4, tooltip = _('If not empty, this username will be always used as credential'))
    fixedPassword = gui.PasswordField(label=_('Password'), order = 5, tooltip = _('If not empty, this password will be always used as credential'))
    listenPort = gui.NumericField(label=_('Listen port'), length = 5, order = 6, tooltip = _('Listening port of NX (ssh) at client machine'), defvalue = '22')
    connection = gui.ChoiceField(label=_('Connection'), order = 7, tooltip = _('Connection speed for this transport (quality)'), values = [
            {'id' : 'modem', 'text' : 'modem'},
            {'id' : 'isdn', 'text' : 'isdn'},
            {'id' : 'adsl', 'text' : 'adsl'},
            {'id' : 'wan', 'text' : 'wan'},
            {'id' : 'lan', 'text' : 'lan'},
        ] )
    session = gui.ChoiceField(label=_('Session'), order = 8, tooltip = _('Desktop session'), values = [
            {'id' : 'gnome', 'text' : 'gnome'},
            {'id' : 'kde', 'text' : 'kde'},
            {'id' : 'cde', 'text' : 'cde'},
        ] )
    cacheDisk = gui.ChoiceField(label=_('Disk Cache'), order = 9, tooltip = _('Cache size en Mb stored at disk'), values = [
            {'id' : '0', 'text' : '0 Mb'},
            {'id' : '32', 'text' : '32 Mb'},
            {'id' : '64', 'text' : '64 Mb'},
            {'id' : '128', 'text' : '128 Mb'},
            {'id' : '256', 'text' : '256 Mb'},
            {'id' : '512', 'text' : '512 Mb'},
        ] ) 
    cacheMem = gui.ChoiceField(label=_('Memory Cache'), order = 10, tooltip = _('Cache size en Mb keept at memory'), values = [
            {'id' : '4', 'text' : '4 Mb'},
            {'id' : '8', 'text' : '8 Mb'},
            {'id' : '16', 'text' : '16 Mb'},
            {'id' : '32', 'text' : '32 Mb'},
            {'id' : '64', 'text' : '64 Mb'},
            {'id' : '128', 'text' : '128 Mb'},
        ] ) 
    
    
    def __init__(self, environment, values = None):
        super(TSNXTransport, self).__init__(environment, values)
        if values != None:
            if values['tunnelServer'].find(':') == -1:
                raise Transport.ValidationException(_('Must use HOST:PORT in Tunnel Server Field'))
            self._tunnelServer = values['tunnelServer']
            self._tunnelCheckServer = values['tunnelCheckServer']
            self._useEmptyCreds = gui.strToBool(values['useEmptyCreds'])
            self._fixedName = values['fixedName']
            self._fixedPassword = values['fixedPassword']
            self._listenPort = values['listenPort']
            self._connection = values['connection']
            self._session = values['session']
            self._cacheDisk = values['cacheDisk']
            self._cacheMem = values['cacheMem']
        else:
            self._tunnelServer = ''
            self._tunnelCheckServer = ''
            self._useEmptyCreds = ''
            self._fixedName = ''
            self._fixedPassword = ''
            self._listenPort = ''
            self._connection = ''
            self._session = ''
            self._cacheDisk = ''
            self._cacheMem = ''
    
    def marshal(self):
        '''
        Serializes the transport data so we can store it in database
        '''
        return str.join( '\t', [ 'v1', gui.boolToStr(self._useEmptyCreds), self._fixedName, self._fixedPassword, self._listenPort,
                                self._connection, self._session, self._cacheDisk, self._cacheMem, self._tunnelServer, self._tunnelCheckServer ] ) 
    
    def unmarshal(self, string):
        data = string.split('\t')
        if data[0] == 'v1':
            self._useEmptyCreds = gui.strToBool(data[1])
            self._fixedName, self._fixedPassword, self._listenPort, self._connection, self._session, self._cacheDisk, self._cacheMem, self._tunnelServer, self._tunnelCheckServer = data[2:]
            
        
    def valuesDict(self):
        return {  'useEmptyCreds' : gui.boolToStr(self._useEmptyCreds), 'fixedName' : self._fixedName, 
                'fixedPassword' : self._fixedPassword, 'listenPort': self._listenPort,
                'connection' : self._connection, 'session' : self._session, 'cacheDisk' : self._cacheDisk,
                'cacheMem' : self._cacheMem, 'tunnelServer' : self._tunnelServer, 
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
            if connection.testServer(ip, self._listenPort) == True:
                self.cache().put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            else:
                self.cache().put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'
    
    def renderForHtml(self, userService, idUserService, idTransport, ip, os, user, password):
        
        prefs = user.prefs('nx')
        
        username = user.getUsernameForAuth()
        proc = username.split('@')
        username = proc[0]
        if self._fixedName is not '':
            username = self._fixedName
        if self._fixedPassword is not '':
            password = self._fixedPassword
        if self._useEmptyCreds is True:
            username, password  = '',''
            
        width, height = CommonPrefs.getWidthHeight(prefs)
        cache = Cache('pam')


        tunuser = ''.join(random.choice(string.letters + string.digits) for i in xrange(12)) + ("%f" % time.time()).split('.')[1]
        tunpass = ''.join(random.choice(string.letters + string.digits) for i in xrange(12))
        cache.put(tunuser, tunpass, 60*10) # Credential valid for ten minutes, and for 1 use only
        
        sshHost, sshPort = self._tunnelServer.split(':')
        
        logger.debug('Username generated: {0}, password: {1}'.format(tunuser, tunpass))
        tun = "{0} {1} {2} {3} {4} {5} {6}".format(tunuser, tunpass, sshHost, sshPort, ip, self._listenPort, '9')
            
        # Extra data
        extra = { 'width': width, 'height' : height,
                 'connection' : self._connection,
                 'session' : self._session, 'cacheDisk': self._cacheDisk,
                 'cacheMem' : self._cacheMem, 'tun' : tun }
            
        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)
            
        return generateHtmlForNX(self, idUserService, idTransport, os, username, password, extra)
        
    def getHtmlComponent(self, theId, os, componentId):
        # We use helper to keep this clean
        return getHtmlComponent(self.__module__, componentId)
    