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
from django.utils.translation import ugettext_noop as _
from uds.core.auths import Authenticator
from uds.core.managers.CryptoManager import CryptoManager
from uds.models import Authenticator as dbAuthenticator
from uds.core.util.State import State
import hashlib
import logging

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


    def __init__(self, dbAuth, environment, values = None):
        super(InternalDBAuth, self).__init__(dbAuth, environment, values)
        # Ignore values
    
    def valuesDict(self):
        res = {}
        return res

    def __str__(self):
        return "Internal DB Authenticator Authenticator"
    
    def marshal(self):
        return "v1"
    
    def unmarshal(self, str_):
        data = str_.split('\t')
        if data[0] == 'v1':
            pass
        
    def authenticate(self, username, credentials, groupsManager):
        logger.debug('Username: {0}, Password: {1}'.format(username, credentials))
        auth = self.dbAuthenticator()
        try:
            usr = auth.users.filter(name=username, state=State.ACTIVE)
            if len(usr) == 0:
                return False
            usr = usr[0]
            # Internal Db Auth has its own groups, and if it active it is valid
            if usr.password == hashlib.sha1(credentials).hexdigest():
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

        
            
    