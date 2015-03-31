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
from uds.core.util import connection

import logging

logger = logging.getLogger(__name__)

READY_CACHE_TIMEOUT = 30


class X2GOTransport(Transport):
    '''
    Provides access via RDP to service.
    This transport can use an domain. If username processed by authenticator contains '@', it will split it and left-@-part will be username, and right password
    '''
    typeName = _('X2GO Transport (direct)')
    typeType = 'X2GOTransport'
    typeDescription = _('X2GO Transport for direct connection')
    iconFile = 'x2go.png'
    protocol = protocols.NX

    useEmptyCreds = gui.CheckBoxField(label=_('Empty creds'), order=1, tooltip=_('If checked, the credentials used to connect will be emtpy'))
    fixedName = gui.TextField(label=_('Username'), order=2, tooltip=_('If not empty, this username will be always used as credential'))
    fixedPassword = gui.PasswordField(label=_('Password'), order=3, tooltip=_('If not empty, this password will be always used as credential'))
    listenPort = gui.NumericField(label=_('Listening port'), length=5, order=4, tooltip=_('Listening port of NX (ssh) at client machine'), defvalue='22')
    connection = gui.ChoiceField(label=_('Connection'), order=6, tooltip=_('Connection speed for this transport (quality)'),
                                 values=[
                                     {'id': 'modem', 'text': 'modem'},
                                     {'id': 'isdn', 'text': 'isdn'},
                                     {'id': 'adsl', 'text': 'adsl'},
                                     {'id': 'wan', 'text': 'wan'},
                                     {'id': 'lan', 'text': 'lan'}
    ])
    session = gui.ChoiceField(label=_('Session'), order=7, tooltip=_('Desktop session'),
                              values=[
                                  {'id': 'gnome', 'text': 'gnome'},
                                  {'id': 'kde', 'text': 'kde'},
                                  {'id': 'cde', 'text': 'cde'},
    ])
    cacheDisk = gui.ChoiceField(label=_('Disk Cache'), order=8, tooltip=_('Cache size en Mb stored at disk'),
                                values=[
                                    {'id': '0', 'text': '0 Mb'},
                                    {'id': '32', 'text': '32 Mb'},
                                    {'id': '64', 'text': '64 Mb'},
                                    {'id': '128', 'text': '128 Mb'},
                                    {'id': '256', 'text': '256 Mb'},
                                    {'id': '512', 'text': '512 Mb'},
    ])
    cacheMem = gui.ChoiceField(label=_('Memory Cache'), order=9, tooltip=_('Cache size en Mb kept at memory'),
                               values=[
                                       {'id': '4', 'text': '4 Mb'},
                                       {'id': '8', 'text': '8 Mb'},
                                       {'id': '16', 'text': '16 Mb'},
                                       {'id': '32', 'text': '32 Mb'},
                                       {'id': '64', 'text': '64 Mb'},
                                       {'id': '128', 'text': '128 Mb'},
    ])

    def initialize(self, values):
        if values is None:
            return
        # Just pass over in fact

    def isAvailableFor(self, ip):
        '''
        Checks if the transport is available for the requested destination ip
        Override this in yours transports
        '''
        logger.debug('Checking availability for {0}'.format(ip))
        ready = self.cache().get(ip)
        if ready is None:
            # Check again for readyness
            if connection.testServer(ip, self.listenPort.value) is True:
                self.cache().put(ip, 'Y', READY_CACHE_TIMEOUT)
                return True
            else:
                self.cache().put(ip, 'N', READY_CACHE_TIMEOUT)
        return ready == 'Y'

    def getUDSTransportScript(self, userService, transport, ip, os, user, password, request):
        logger.debug('Getting X2Go Transport info')

        prefs = user.prefs('nx')

        username = user.getUsernameForAuth()
        proc = username.split('@')
        username = proc[0]
        if self.fixedName.value != '':
            username = self.fixedName.value
        if self.fixedPassword.value != '':
            password = self.fixedPassword.value
        if self.useEmptyCreds.isTrue():
            username, password = '', ''

        # We have the credentials right now, let os manager

        width, height = CommonPrefs.getWidthHeight(prefs)

        # Fix username/password acording to os manager
        username, password = userService.processUserPassword(username, password)

        # data
        data = {
            'username': username,
            'password': password,
            'width': width,
            'height': height,
            'port': self.listenPort.value,
            'connection': self.connection.value,
            'session': self.session.value,
            'cacheDisk': self.cacheDisk.value,
            'cacheMem': self.cacheMem.value
        }

        return '''
from PyQt4 import QtCore, QtGui
import six
from uds import osDetector

data = {data}
osname = {os}

QtGui.QMessageBox.critical(parent, 'Notice ' + osDetector.getOs(), six.text_type(data), QtGui.QMessageBox.Ok)
'''.format(data=data, os=os)

