# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core import osmanagers
from uds.osmanagers.LinuxOsManager import LinuxOsManager
from uds.core.util import log
from uds.core.util import encoders

import logging

logger = logging.getLogger(__name__)


class LinuxRandomPassManager(LinuxOsManager):
    typeName = _('Linux Random Password OS Manager')
    typeType = 'LinRandomPasswordManager'
    typeDescription = _('Os Manager to control linux machines, with user password set randomly.')
    iconFile = 'losmanager.png'

    # Apart form data from linux os manager, we need also domain and credentials
    userAccount = gui.TextField(length=64, label=_('Account'), order=2, tooltip=_('User account to change password'), required=True)

    # Inherits base "onLogout"
    onLogout = LinuxOsManager.onLogout
    idle = LinuxOsManager.idle

    def __init__(self, environment, values):
        super(LinuxRandomPassManager, self).__init__(environment, values)
        if values is not None:
            if values['userAccount'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide an user account!!!'))
            self._userAccount = values['userAccount']
        else:
            self._userAccount = ''

    def release(self, service):
        super(LinuxRandomPassManager, self).release(service)

    def processUserPassword(self, service, username, password):
        if username == self._userAccount:
            return [username, service.recoverValue('linOsRandomPass')]
        return [username, password]

    def genPassword(self, service):
        import random
        import string
        randomPass = service.recoverValue('linOsRandomPass')
        if randomPass is None:
            randomPass = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
            service.storeValue('linOsRandomPass', randomPass)
            log.doLog(service, log.INFO, "Password set to \"{}\"".format(randomPass), log.OSMANAGER)

        return randomPass

    def infoVal(self, service):
        return 'rename:{0}\t{1}\t\t{2}'.format(self.getName(service), self._userAccount, self.genPassword(service))

    def infoValue(self, service):
        return 'rename\r{0}\t{1}\t\t{2}'.format(self.getName(service), self._userAccount, self.genPassword(service))

    def marshal(self):
        base = super(LinuxRandomPassManager, self).marshal()
        '''
        Serializes the os manager data so we can store it in database
        '''
        return '\t'.join(['v1', self._userAccount, encoders.encode(base, 'hex', asText=True)]).encode('utf8')

    def unmarshal(self, s):
        data = s.decode('utf8').split('\t')
        if data[0] == 'v1':
            self._userAccount = data[1]
            super(LinuxRandomPassManager, self).unmarshal(encoders.decode(data[2], 'hex'))

    def valuesDict(self):
        dic = super(LinuxRandomPassManager, self).valuesDict()
        dic['userAccount'] = self._userAccount
        return dic
