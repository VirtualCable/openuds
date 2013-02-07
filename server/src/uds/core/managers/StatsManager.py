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

from uds.models import Provider
from uds.models import Service
from uds.models import DeployedService
from uds.models import StatsCounters
from uds.models import StatsEvents

import logging

logger = logging.getLogger(__name__)


PROVIDER_OWNER_TYPE, SERVICE_OWNER_TYPE, DEPLOYED_OWNER_TYPE = xrange(3)

# hierarchy of owners
parentsDict = {
        PROVIDER_OWNER_TYPE: None,
        SERVICE_OWNER_TYPE: PROVIDER_OWNER_TYPE,
        DEPLOYED_OWNER_TYPE: SERVICE_OWNER_TYPE,
    }
# Dict to convert objects to owner types
# Dict for translations
transDict = {
        DeployedService : DEPLOYED_OWNER_TYPE,
        Service : SERVICE_OWNER_TYPE,
        Provider : PROVIDER_OWNER_TYPE
    }


class StatsManager(object):
    '''
    Manager for loggins statistics, so we can provide usefull info about platform usage
    
    Right now, we are going to provide an interface to "counter stats", that is, statistics
    that has counters (such as how many users is at a time active at platform, how many services
    are assigned, are in use, in cache, etc...
    '''
    _manager = None
    
    def __init__(self):
        pass
    
    @staticmethod
    def manager():
        if StatsManager._manager == None:
            StatsManager._manager = StatsManager()
        return StatsManager._manager
    

    def __getOwner(self, fromObject):
        '''
        Gets the owner type/id for the specified object, or raises an exception if unknown
        '''
        owner_type = transDict[type(fromObject)]
        owner_id = fromObject.id
        return (owner_type, owner_id)
    
    # Counter stats
    def addCounter(self, toWhat, counterType, counterValue, stamp = None):
        '''
        Adds a new counter stats to database.
        
        Args:
            
            toWhat: if of the counter
            counterType: The type of counter that will receive the value (i.e. STORAGE_COUNTER_TYPE, LOAD_COUNTER_TYPE
            counterValue: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:
            
            Nothing       
        '''
        from uds.models import getSqlDatetime
        import time
        
        if stamp is None:
            stamp = getSqlDatetime()
        
        # To Unix epoch
        stamp = int(time.mktime(stamp.timetuple()))
        
        try:
            (owner_type, owner_id) = self.__getOwner(toWhat)
        except:
            logger.error('Unhandled stats fo object type {0} and counter type {1}'.format(toWhat, counterType))
            return
        
        try:
            StatsCounters.objects.create(owner_id=owner_id, owner_type=owner_type, counter_type=counterType, value=counterValue, stamp=stamp)
            return True
        except:
            logger.error('Exception handling stats saving (maybe database is full?)')
        return False
         
    
    def removeCounters(self, fromWat):
        '''
        Removes counters from item

        Args:
            
            fromWhat: if of the counter
            counter: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:
            
            Nothing       
        '''
        pass
    
    def getCounters(self, counterType, **kwargs):
        '''
        Retrieves counters from item

        Args:
        
            counterTye: Type of counter to get values
            counterId: (optional), if specified, limit counter to only this id, all ids for specidied type if not
            maxElements: (optional) Maximum number of elements to retrieve, all if nothing specified
            from: date from what to obtain counters. Unlimited if not specified
            to: date until obtain counters. Unlimited if not specified
            
        Returns:
            
            Iterator, containing (date, counter) each element
        '''
        
    
    def cleanupCounter(self):
        '''
        Removes all counters previous to configured max keep time for stat information from database.
        '''
        pass
    
    # Event stats
    # Counter stats
    def addEvent(self, toWhat, stamp = None):
        '''
        Adds a new counter stat to database.
        
        Args:
            
            toWhat: if of the counter
            counter: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:
            
            Nothing       
                   

        '''
        pass
    
    def removeEvents(self, fromWhat):
        '''
        Removes counters from item

        Args:
            
            toWhat: if of the counter
            counter: Counter to store. Right now, this must be an integer value (-2G ~ 2G)
            stamp: if not None, this will be used as date for cuounter, else current date/time will be get
                   (this has a granurality of seconds)

        Returns:
            
            Nothing       
        '''
        pass
    
    
    def getEvents(self, fromWhat, **kwargs):
        '''
        Retrieves counters from item

        Args:
        
            fromWhat: From what object to get counters
            maxElements: (optional) Maximum number of elements to retrieve

        Returns:
            
            Array of lists, containing (date, counter)
                   
        '''
    
    def cleanupEvents(self):
        '''
        Removes all counters previous to configured max keep time for stat information from database.
        '''
        pass

    