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


from uds.models import UserService
from uds.models import DeployedServicePublication
from uds.models import DeployedService
from uds.models import Service
from uds.models import Provider
from uds.models import User
from uds.models import Group
from uds.models import Authenticator

from uds.core.util import log

from uds.core.util.Config import GlobalConfig

import logging

logger = logging.getLogger(__name__)

OT_USERSERVICE, OT_PUBLICATION, OT_DEPLOYED_SERVICE, OT_SERVICE, OT_PROVIDER, OT_USER, OT_GROUP, OT_AUTHENTICATOR = xrange(8)

# Dict for translations
transDict = {
        UserService : OT_USERSERVICE,
        DeployedServicePublication : OT_PUBLICATION,
        DeployedService : OT_DEPLOYED_SERVICE,
        Service : OT_SERVICE,
        Provider : OT_PROVIDER,
        User : OT_USER,
        Group : OT_GROUP,
        Authenticator : OT_AUTHENTICATOR
    }
    
class LogManager(object):
    '''
    Manager for logging (at database) events
    '''
    _manager = None
    
    def __init__(self):
        pass
    
    @staticmethod
    def manager():
        if LogManager._manager == None:
            LogManager._manager = LogManager()
        return LogManager._manager

    def __log(self, owner_type, owner_id, level, message, source):
        '''
        Logs a message associated to owner
        '''
        from uds.models import getSqlDatetime
        from uds.models import Log
        
        qs = Log.objects.filter(owner_id = owner_id, owner_type = owner_type)
        # First, ensure we do not have more than requested logs, and we can put one more log item
        if qs.count() >= GlobalConfig.MAX_LOGS_PER_ELEMENT.getInt():
            for i in qs.order_by('-created',)[GlobalConfig.MAX_LOGS_PER_ELEMENT.getInt()-1:]: i.delete()
            
        # now, we add new log
        Log.objects.create(owner_type = owner_type, owner_id = owner_id, created = getSqlDatetime(), source = source, level = level, data = message)


    def __getLogs(self, owner_type, owner_id, limit):
        '''
        Get all logs associated with an user service, ordered by date
        '''
        from uds.models import Log

        qs = Log.objects.filter(owner_id = owner_id, owner_type = owner_type)
        return [{'date': x.created, 'level': x.level, 'source': x.source, 'message': x.data} for x in reversed(qs.order_by('-created')[:limit])]
    
    def __clearLogs(self, owner_type, owner_id):
        '''
        Clears all logs related to user service
        '''
        from uds.models import Log

        Log.objects.filter(owner_id = owner_id, owner_type = owner_type).delete()
       
    
    
    def doLog(self, wichObject, level, message, source):
        '''
        Do the logging for the requested object.
        
        If the object provided do not accepts associated loggin, it simply ignores the request
        '''
        if type(level) is not int:
            level = log.logLevelFromStr(level)
        
        owner_type = transDict.get(type(wichObject), None)
        if owner_type is not None: 
            self.__log(owner_type, wichObject.id, level, message, source)
        else:
            logger.debug('Requested doLog for a type of object not covered: {0}'.format(wichObject))
            
        
    def getLogs(self, wichObject, limit):
        '''
        Get the logs associated with "wichObject", limiting to "limit" (default is GlobalConfig.MAX_LOGS_PER_ELEMENT) 
        '''
        
        owner_type = transDict.get(type(wichObject), None)

        if owner_type is not None: 
            return self.__getLogs(owner_type, wichObject.id, limit)
        else:
            logger.debug('Requested getLogs for a type of object not covered: {0}'.format(wichObject))
            return []
            
    def clearLogs(self, wichObject):
        '''
        Clears all logs related to wichObject
        
        Used mainly at object database removal (parent object)
        '''
        
        owner_type = transDict.get(type(wichObject), None)
        if owner_type is not None: 
            self.__clearLogs(owner_type, wichObject.id)
        else:
            logger.debug('Requested clearLogs for a type of object not covered: {0}'.format(wichObject))
