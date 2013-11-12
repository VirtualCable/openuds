# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

from uds.core.util.Config import GlobalConfig
from uds.models import Authenticator, User

from uds.REST import Handler, HandlerError

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /auth path

class Login(Handler):
    path = 'auth' 
    authenticated = False # Public method
    
    def post(self):
        '''
        This login uses parameters to generate auth token
        The alternative is to use the template tag inside "REST" that is called auth_token, that extracts an auth token from an user session
        We can use any of this forms due to the fact that the auth token is in fact a session key
        Parameters:
            mandatory:
                username:
                password:
                auth:
            optional:
                locale: (defaults to "en")
        Result:
            on success: { 'result': 'ok', 'auth': [auth_code] }
            on error: { 'result: 'error', 'error': [error string] }
        '''
        try:
            username, auth, password = self._params['username'], self._params['auth'], self._params['password']
            locale = self._params.get('locale', 'en')
            if auth == 'admin':
                if GlobalConfig.SUPER_USER_LOGIN.get(True) == username and GlobalConfig.SUPER_USER_PASS.get(True) == password:
                    self.genAuthToken(-1, username, locale, True, True)
                    return{'result': 'ok', 'token': self.getAuthToken()}
                else:
                    raise Exception('Invalid credentials')
            raise Exception('Invalid Credentials')
        except Exception as e:
            logger.exception('exception')
            return {'result': 'error', 'error': unicode(e)}
        
    
class Logout(Handler):
    path = 'auth'
    authenticated = True # By default, all handlers needs authentication
    
    def get(self):
        # Remove auth token
        self.cleanAuthToken()
        return 'done'        
        
    def post(self):
        return self.get()
    
class Auths(Handler):
    path = 'auth'
    authenticated = False # By default, all handlers needs authentication
    
    def auths(self):
        for a in Authenticator.all():
            if a.getType().isCustom() is False:
                yield { 'auth' : str(a.small_name), 'name' : a.name }
    
    def get(self):
        return list(self.auths())
        
        