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


"""
Created on Jul 29, 2011

@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from django.utils.translation import ugettext_noop as _
from uds.core.managers.UserPrefsManager import CommonPrefs
from uds.core.ui.UserInterface import gui
from uds.core.transports.BaseTransport import Transport
from uds.core.transports.BaseTransport import TUNNELED_GROUP
from uds.core.transports import protocols
from uds.models import TicketStore
from uds.core.util import OsDetector
from uds.core.util.tools import DictAsObj
from .NXFile import NXFile

import logging
import random
import string
import os

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class TSNXTransport(Transport):
    """
    Provides access via NX to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    """
    typeName = _('NX v3.5')
    typeType = 'TSNXTransport'
    typeDescription = _('NX protocol v3.5. Tunneled connection.')
    iconFile = 'nx.png'
    protocol = protocols.NX
    group = TUNNELED_GROUP

    tunnelServer = gui.TextField(label=_('Tunnel server'), order=1, tooltip=_('IP or Hostname of tunnel server sent to client device ("public" ip) and port. (use HOST:PORT format)'), tab=gui.TUNNEL_TAB)
    tunnelCheckServer = gui.TextField(label=_('Tunnel host check'), order=2, tooltip=_('If not empty, this server will be used to check if service is running before assigning it to user. (use HOST:PORT format)'), tab=gui.TUNNEL_TAB)

    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=3, tooltip=_('If checked, the credentials used to connect will be emtpy'), tab=gui.CREDENTIALS_TAB)
    fixedName = gui.TextField(label=_('Username'), order=4, tooltip=_('If not empty, this username will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    fixedPassword = gui.PasswordField(label=_('Password'), order=5, tooltip=_('If not empty, this password will be always used as credential'), tab=gui.CREDENTIALS_TAB)
    listenPort = gui.NumericField(label=_('Listening port'), length=5, order=6, tooltip=_('Listening port of NX (ssh) at client machine'), defvalue='22')
    connection = gui.ChoiceField(label=_('Connection'), order=7, tooltip=_('Connection speed for this transport (quality)'),
                                 values=[
                                     {'id': 'modem', 'text': 'modem'},
                                     {'id': 'isdn', 'text': 'isdn'},
                                     {'id': 'adsl', 'text': 'adsl'},
                                     {'id': 'wan', 'text': 'wan'},
                                     {'id': 'lan', 'text': 'lan'},
    ], tab=gui.PARAMETERS_TAB)
    session = gui.ChoiceField(label=_('Session'), order=8, tooltip=_('Desktop session'),
                              values=[
                                  {'id': 'gnome', 'text': 'gnome'},
                                  {'id': 'kde', 'text': 'kde'},
                                  {'id': 'cde', 'text': 'cde'},
    ], tab=gui.PARAMETERS_TAB)
    cacheDisk = gui.ChoiceField(label=_('Disk Cache'), order=9, tooltip=_('Cache size en Mb stored at disk'),
                                values=[
                                    {'id': '0', 'text': '0 Mb'},
                                    {'id': '32', 'text': '32 Mb'},
                                    {'id': '64', 'text': '64 Mb'},
                                    {'id': '128', 'text': '128 Mb'},
                                    {'id': '256', 'text': '256 Mb'},
                                    {'id': '512', 'text': '512 Mb'},
    ], tab=gui.PARAMETERS_TAB)
    cacheMem = gui.ChoiceField(label=_('Memory Cache'), order=10, tooltip=_('Cache size en Mb kept at memory'),
                               values=[
                                   {'id': '4', 'text': '4 Mb'},
                                   {'id': '8', 'text': '8 Mb'},
                                   {'id': '16', 'text': '16 Mb'},
                                   {'id': '32', 'text': '32 Mb'},
                                   {'id': '64', 'text': '64 Mb'},
                                   {'id': '128', 'text': '128 Mb'},
    ], tab=gui.PARAMETERS_TAB)

    def __init__(self, environment, values=None):
        super(TSNXTransport, self).__init__(environment, values)
        if values is not None:
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
        """
        Serializes the transport data so we can store it in database
        """
        return str.join('\t', ['v1', gui.boolToStr(self._useEmptyCreds), self._fixedName, self._fixedPassword, self._listenPort,
                               self._connection, self._session, self._cacheDisk, self._cacheMem, self._tunnelServer, self._tunnelCheckServer])

    def unmarshal(self, string):
        data = string.split('\t')
        if data[0] == 'v1':
            self._useEmptyCreds = gui.strToBool(data[1])
            self._fixedName, self._fixedPassword, self._listenPort, self._connection, self._session, self._cacheDisk, self._cacheMem, self._tunnelServer, self._tunnelCheckServer = data[2:]

    def valuesDict(self):
        return {
            'useEmptyCreds': gui.boolToStr(self._useEmptyCreds),
            'fixedName': self._fixedName,
            'fixedPassword': self._fixedPassword,
            'listenPort': self._listenPort,
            'connection': self._connection,
            'session': self._session,
            'cacheDisk': self._cacheDisk,
            'cacheMem': self._cacheMem,
            'tunnelServer': self._tunnelServer,
            'tunnelCheckServer': self._tunnelCheckServer
        }

    def isAvailableFor(self, userService, ip):
        """
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        """
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache.get(ip)
        if ready is None:
            # Check again for readyness
            if self.testServer(userService, ip, self._listenPort) is True:
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

        tunpass = ''.join(random.choice(string.letters + string.digits) for _i in range(12))
        tunuser = TicketStore.create(tunpass)

        sshServer = self._tunnelServer
        if ':' not in sshServer:
            sshServer += ':443'

        sshHost, sshPort = sshServer.split(':')

        logger.debug('Username generated: {0}, password: {1}'.format(tunuser, tunpass))

        width, height = CommonPrefs.getWidthHeight(prefs)
        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)

        m = {
            'ip': ip,
            'tunUser': tunuser,
            'tunPass': tunpass,
            'tunHost': sshHost,
            'tunPort': sshPort,
            'password': password,
            'port': self._listenPort
        }

        r = NXFile(username=username, password=password, width=width, height=height)
        r.host = '{address}'
        r.port = '{port}'
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
            return super(self.__class__, self).getUDSTransportScript(userService, transport, ip, os, user, password, request)

        return self.getScript('scripts/{}/tunnel.py'.format(os)).format(
            r=r,
            m=DictAsObj(m),
        )

