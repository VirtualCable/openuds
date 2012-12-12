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
from uds.models import UserService, State
import logging

logger = logging.getLogger(__name__)
useLogger = logging.getLogger('useLog')

# Logging levels
OTHER,DEBUG,INFO,WARN,ERROR,FATAL = (10000*(x+1) for x in xrange(6))

# Logging sources
INTERNAL,ACTOR,TRANSPORT = ('internal', 'actor', 'transport')

# Names for defined log levels
__nameLevels = {
     'DEBUG': DEBUG,
     'INFO': INFO,
     'WARN': WARN,
     'ERROR': ERROR,
     'FATAL': FATAL,
     'OTHER': OTHER
    }

# Reverse dict of names
__valueLevels = dict((v,k) for k, v in __nameLevels.iteritems())

def logLevelFromStr(str):
    '''
    Gets the numeric log level from an string.
    '''
    return __nameLevels.get(str, OTHER)

def logStrFromLevel(level):
    return __valueLevels.get(level, 'OTHER')
    

def useLog(type_, serviceUniqueId, serviceIp, username):
    useLogger.info('|'.join([type_, serviceUniqueId, serviceIp, username]))
    