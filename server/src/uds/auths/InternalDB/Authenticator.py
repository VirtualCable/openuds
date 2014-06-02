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
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.auths import Authenticator
from uds.models import Authenticator as dbAuthenticator
from uds.core.ui import gui
from uds.core.util.State import State
import dns
import hashlib
import logging

__updated__ = '2014-06-02'

logger = logging.getLogger(__name__)


class InternalDBAuth(Authenticator):
    typeName = _('Internal Database')
    typeType = 'InternalDBAuth'
    typeDescription = _('Internal dabasase authenticator. Doesn\'t uses external sources')
    iconFile = 'auth.png'

    # If we need to enter the password for this user
    needsPassword = True

    # This is the only internal source
    isExternalSource = False

    differentForEachHost = gui.CheckBoxField(label=_('Different user for each host'), order=1, tooltip=_('If checked, each host will have a different user name'), defvalue="false", rdonly=True)
    reverseDns = gui.CheckBoxField(label=_('Reverse DNS'), order=2, tooltip=_('If checked, the host will be reversed dns'), defvalue="false", rdonly=True)

    def initialize(self, values):
        if values is None:
            return

    def getIp(self, ip):
        if self.reverseDns.isTrue():
            try:
                return str(dns.resolver.query(dns.reversename.from_address(ip), 'PTR')[0])
            except:
                pass
        return ip

    def transformUsername(self, username):
        from uds.core.util.request import getRequest
        if self.differentForEachHost.isTrue():
            newUsername = self.getIp(getRequest().ip) + '-' + username
            # Duplicate basic user into username.
            auth = self.dbAuthenticator()
            # "Derived" users will belong to no group at all, because we will extract groups from "base" user
            # This way also, we protect from using forged "ip" + "username", because those will belong in fact to no group
            # and access will be denied
            try:
                usr = auth.users.get(name=username, state=State.ACTIVE)
                parent = usr.id
                usr.id = None
                if usr.real_name.strip() == '':
                    usr.real_name = usr.name
                usr.name = newUsername
                usr.parent = parent
                usr.save()
            except:
                pass  # User already exists
            username = newUsername

        return username

    def authenticate(self, username, credentials, groupsManager):
        logger.debug('Username: {0}, Password: {1}'.format(username, credentials))
        auth = self.dbAuthenticator()
        try:
            usr = auth.users.filter(name=username, state=State.ACTIVE)
            if len(usr) == 0:
                return False
            usr = usr[0]
            if usr.parent != -1:  # Direct auth not allowed for "derived" users
                return False

            # Internal Db Auth has its own groups, and if it active it is valid
            if usr.password == hashlib.sha1(credentials.encode('utf-8')).hexdigest():
                groupsManager.validate([g.name for g in usr.groups.all()])
                return True
            return False
        except dbAuthenticator.DoesNotExist:
            return False

    def createUser(self, usrData):
        pass

    @staticmethod
    def test(env, data):
        return [True, _("Internal structures seems ok")]

    def check(self):
        return _("All seems fine in the authenticator.")

    def __str__(self):
        return "Internal DB Authenticator Authenticator"
