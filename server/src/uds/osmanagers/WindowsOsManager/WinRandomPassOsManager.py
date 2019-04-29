# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core.managers.CryptoManager import CryptoManager
from uds.core import osmanagers
from .WindowsOsManager import WindowsOsManager
from uds.core.util import log
from uds.core.util import encoders

import logging

logger = logging.getLogger(__name__)


class WinRandomPassManager(WindowsOsManager):
    typeName = _('Windows Random Password OS Manager')
    typeType = 'WinRandomPasswordManager'
    typeDescription = _('Os Manager to control windows machines, with user password set randomly.')
    iconFile = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    userAccount = gui.TextField(length=64, label=_('Account'), order=2, tooltip=_('User account to change password'), required=True)
    password = gui.PasswordField(length=64, label=_('Password'), order=3, tooltip=_('Current (template) password of the user account'), required=True)

    # Inherits base "onLogout"
    onLogout = WindowsOsManager.onLogout
    idle = WindowsOsManager.idle

    def __init__(self, environment, values):
        super(WinRandomPassManager, self).__init__(environment, values)
        if values is not None:
            if values['userAccount'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide an user account!!!'))
            if values['password'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide a password for the account!!!'))
            self._userAccount = values['userAccount']
            self._password = values['password']
        else:
            self._userAccount = ''
            self._password = ""

    def release(self, service):
        super(WinRandomPassManager, self).release(service)

    def processUserPassword(self, service, username, password):
        if username == self._userAccount:
            password = service.recoverValue('winOsRandomPass')

        return WindowsOsManager.processUserPassword(self, service, username, password)

    def genPassword(self, service):
        import random
        import string
        randomPass = service.recoverValue('winOsRandomPass')
        if randomPass is None:
            randomPass = ''.join(random.SystemRandom().choice(string.ascii_letters + string.digits) for _ in range(16))
            service.storeValue('winOsRandomPass', randomPass)
            log.doLog(service, log.INFO, "Password set to \"{}\"".format(randomPass), log.OSMANAGER)
        return randomPass

    def infoVal(self, service):
        return 'rename:{0}\t{1}\t{2}\t{3}'.format(self.getName(service), self._userAccount, self._password, self.genPassword(service))

    def infoValue(self, service):
        return 'rename\r{0}\t{1}\t{2}\t{3}'.format(self.getName(service), self._userAccount, self._password, self.genPassword(service))

    def marshal(self):
        base = super(WinRandomPassManager, self).marshal()
        '''
        Serializes the os manager data so we can store it in database
        '''
        return '\t'.join(['v1', self._userAccount, CryptoManager.manager().encrypt(self._password), encoders.encode(base, 'hex', asText=True)]).encode('utf8')

    def unmarshal(self, s):
        data = s.decode('utf8').split('\t')
        if data[0] == 'v1':
            self._userAccount = data[1]
            self._password = CryptoManager.manager().decrypt(data[2])
            super(WinRandomPassManager, self).unmarshal(encoders.decode(data[3], 'hex'))

    def valuesDict(self):
        dic = super(WinRandomPassManager, self).valuesDict()
        dic['userAccount'] = self._userAccount
        dic['password'] = self._password
        return dic
