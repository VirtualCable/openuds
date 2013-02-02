# -*- coding: utf-8 -*-

#
# Copyright (c) 2013 Virtual Cable S.L.
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

from django.utils.translation import ugettext as _
from ..auths.AdminAuth import needs_credentials
from ..util.Exceptions import FindException
from uds.core.util import log

from uds.models import UserService
from uds.models import User
from uds.models import Authenticator

import logging

logger = logging.getLogger(__name__)

@needs_credentials
def getUserServiceLogs(credentials, id):
    try:
        us = UserService.objects.get(pk=id)
        return log.getLogs(us)
    except:
        raise FindException(_('Service does not exists'))
    
@needs_credentials
def getUserLogs(credentials, id):
    try:
        user = User.objects.get(pk=id)
        return log.getLogs(user)
    except:
        raise FindException('User does not exists')
    
@needs_credentials
def getAuthLogs(credentials, id):
    try:
        auth = Authenticator.objects.get(pk=id)
        return log.getLogs(auth)
    except:
        raise FindException('Authenticator does not exists')
        
    
# Registers XML RPC Methods
def registerLogFunctions(dispatcher):
    dispatcher.register_function(getUserServiceLogs, 'getUserServiceLogs')
    dispatcher.register_function(getUserLogs, 'getUserLogs')
    dispatcher.register_function(getAuthLogs, 'getAuthLogs')
