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
from uds.core.transports import protocols
from uds.core.util import OsDetector
from uds.core.util import connection
from .NXFile import NXFile

import logging
import os

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class NXTransport(Transport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('NX Transport (direct)')
    typeType = 'NXTransport'
    typeDescription = _('NX Transport for direct connection')
    iconFile = 'nx.png'
    needsJava = True  # If this transport needs java for rendering
    protocol = protocols.NX

    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=1, tooltip=_('If checked, the credentials used to connect will be emtpy'), tab=gui.CREDENTIALS_TAB)
    fixedName = gui.TextField(label=_('Username'), order=2, tooltip=_('If not empty, this username will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    fixedPassword = gui.PasswordField(label=_('Password'), order=3, tooltip=_('If not empty, this password will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    listenPort = gui.NumericField(label=_('Listening port'), length=5, order=4, tooltip=_('Listening port of NX (ssh) at client machine'), defvalue='22')
    connection = gui.ChoiceField(label=_('Connection'), order=6, tooltip=_('Connection speed for this transport (quality)'),
                                 values=[
                                     {'id': 'modem', 'text': 'modem'},
                                     {'id': 'isdn', 'text': 'isdn'},
                                     {'id': 'adsl', 'text': 'adsl'},
                                     {'id': 'wan', 'text': 'wan'},
                                     {'id': 'lan', 'text': 'lan'}
    ], tab=gui.PARAMETERS_TAB)
    session = gui.ChoiceField(label=_('Session'), order=7, tooltip=_('Desktop session'),
                              values=[
                                  {'id': 'gnome', 'text': 'gnome'},
                                  {'id': 'kde', 'text': 'kde'},
                                  {'id': 'cde', 'text': 'cde'},
    ], tab=gui.PARAMETERS_TAB)
    cacheDisk = gui.ChoiceField(label=_('Disk Cache'), order=8, tooltip=_('Cache size en Mb stored at disk'),
                                values=[
                                    {'id': '0', 'text': '0 Mb'},
                                    {'id': '32', 'text': '32 Mb'},
                                    {'id': '64', 'text': '64 Mb'},
                                    {'id': '128', 'text': '128 Mb'},
                                    {'id': '256', 'text': '256 Mb'},
                                    {'id': '512', 'text': '512 Mb'},
    ], tab=gui.PARAMETERS_TAB)
    cacheMem = gui.ChoiceField(label=_('Memory Cache'), order=9, tooltip=_('Cache size en Mb kept at memory'),
                               values=[
                                   {'id': '4', 'text': '4 Mb'},
                                   {'id': '8', 'text': '8 Mb'},
                                   {'id': '16', 'text': '16 Mb'},
                                   {'id': '32', 'text': '32 Mb'},
                                   {'id': '64', 'text': '64 Mb'},
                                   {'id': '128', 'text': '128 Mb'},
    ], tab=gui.PARAMETERS_TAB)

    def __init__(self, environment, values=None):
        super(NXTransport, self).__init__(environment, values)
        if values is not None:
            self._useEmptyCreds = gui.strToBool(values['useEmptyCreds'])
            self._fixedName = values['fixedName']
            self._fixedPassword = values['fixedPassword']
            self._listenPort = values['listenPort']
            self._connection = values['connection']
            self._session = values['session']
            self._cacheDisk = values['cacheDisk']
            self._cacheMem = values['cacheMem']
        else:
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
        return str.join('\t', ['v1', gui.boolToStr(self._useEmptyCreds), self._fixedName, self._fixedPassword, self._listenPort,
                               self._connection, self._session, self._cacheDisk, self._cacheMem])

    def unmarshal(self, string):
        data = string.split('\t')
        if data[0] == 'v1':
            self._useEmptyCreds = gui.strToBool(data[1])
            self._fixedName, self._fixedPassword, self._listenPort, self._connection, self._session, self._cacheDisk, self._cacheMem = data[2:]

    def valuesDict(self):
        return {
            'useEmptyCreds': gui.boolToStr(self._useEmptyCreds),
            'fixedName': self._fixedName,
            'fixedPassword': self._fixedPassword,
            'listenPort': self._listenPort,
            'connection': self._connection,
            'session': self._session,
            'cacheDisk': self._cacheDisk,
            'cacheMem': self._cacheMem
        }

    def isAvailableFor(self, userService, ip):
        '''
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        '''
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for readyness
            if connection.testServer(ip, self._listenPort) is True:
                self.cache.put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            else:
                self.cache.put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def getScript(self, script):
        with open(os.path.join(os.path.dirname(__file__), script)) as f:
            data = f.read()
        return data

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        prefs = user.prefs('nx')

        username = user.getUsernameForAuth()
        proc = username.split('@')
        username = proc[0]
        if self._fixedName is not '':
            username = self._fixedName
        if self._fixedPassword is not '':
            password = self._fixedPassword
        if self._useEmptyCreds is True:
            username, password = '', ''

        # We have the credentials right now, let os manager

        width, height = CommonPrefs.getWidthHeight(prefs)

        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)

        r = NXFile(username=username, password=password, width=width, height=height)
        r.host = ip
        r.port = self._listenPort
        r.connection = self._connection
        r.desktop = self._session
        r.cachedisk = self._cacheDisk
        r.cachemem = self._cacheMem

        os = {
            OsDetector.Windows: 'windows',
            OsDetector.Linux: 'linux',
            OsDetector.Macintosh: 'macosx'

        }.get(os['OS'])

        if os is None:
            return super(NXTransport, self).getUDSTransportScript(self, userService, transport, ip, os, user, password, request)

        return self.getScript('scripts/{}/direct.py'.format(os)).format(r=r)
