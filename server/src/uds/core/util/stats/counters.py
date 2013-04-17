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
from __future__ import unicode_literals

from uds.models import NEVER
from django.utils.translation import ugettext_lazy as _
from uds.core.managers import statsManager
import datetime
import logging

logger = logging.getLogger(__name__)

# Posible counters, note that not all are used by every posible type
# FIRST_COUNTER_TYPE, LAST_COUNTER_TYPE are just a placeholder for sanity checks 
(
    CT_LOAD, CT_STORAGE, CT_ASSIGNED, CT_INUSE, 
) = xrange(4)

__caRead = None
__caWrite = None
__transDict = None
__typeTitles = None


def addCounter(obj, counterType, counterValue, stamp = None):
    '''
    Adds a counter stat to specified object
    
    Although any counter type can be added to any object, there is a relation that must be observed
    or, otherway, the stats will not be recoverable at all:
    
        
    note: Runtime checks are done so if we try to insert an unssuported stat, this won't be inserted and it will be logged
    '''
    if type(obj) not in __caWrite.get(counterType, ()):
        logger.error('Type {0} does not accepts counter of type {1}',format(type(obj), counterValue))
        return False
        
    return statsManager().addCounter(__transDict[type(obj)], obj.id, counterType, counterValue, stamp)
    
    
def getCounters(obj, counterType, **kwargs):
    '''
    Get counters
    
    Args:
        obj: Obj for which to recover stats counters
        counterType: type of counter to recover
        since: (optional, defaults to 'Since beginning') Start date for counters to recover
        to: (optional, defaults to 'Until end') En date for counter to recover
        limit: (optional, defaults to 1000) Number of counter to recover. This is an 'At most' advice. The returned number of value
               can be lower, or even 1 more than requested due to a division for retrieving object at database
        all: (optinal), indicates that get all counters for the type of obj passed in, not only for that obj. 
               
    Returns:
        A generator, that contains pairs of (stamp, value) tuples
    '''
    
    since = kwargs.get('since', NEVER)
    to = kwargs.get('to', datetime.datetime.now())
    limit = kwargs.get('limit', 1000)
    use_max = kwargs.get('use_max', False)
    
    readFncTbl = __caRead.get(type(obj), None)

    
    if readFncTbl is None:
        logger.error('Type {0} has no registered stats'.format(type(obj)))
        return

    fnc = readFncTbl.get(counterType, None)
    
    if fnc is None:
        logger.error('Type {0} has no registerd stats of type {1}'.format(type(obj), counterType))
        return
    
    if kwargs.get('all', None) is not True:
        owner_ids = fnc(obj)
    else:
        owner_ids = None
        
    
    for i in statsManager().getCounters(__transDict[type(obj)], counterType, owner_ids, since, to, limit, use_max):
        val = (datetime.datetime.fromtimestamp(i.stamp), i.value)
        yield val
        
def getCounterTitle(counterType):
    return __typeTitles.get(counterType, '').title()

# Data initialization  
def _initializeData():
    '''
    Initializes dictionaries.
    
    Hides data from global var space
    '''
    from uds.models import Provider, Service, DeployedService
    
    global __caWrite
    global __caRead
    global __transDict
    global __typeTitles
    
    __caWrite = {
        CT_LOAD: (Provider,),
        CT_STORAGE: (Service,),
        CT_ASSIGNED: (DeployedService,),
        CT_INUSE: (DeployedService,),
    }
    
    
    # OBtain  ids from variups type of object to retrieve stats
    def get_Id(obj):
        return obj.id
    
    def get_P_S_Ids(provider):
        return (i.id for i in provider.services.all())
    
    def get_S_DS_Ids(service):
        return (i.id for i in service.deployedServices.all())
    
    def get_P_S_DS_Ids(provider):
        res = ()
        for i in provider.services.all():
            res += get_S_DS_Ids(i)
        return res
    
    __caRead = {
            Provider: {
                CT_LOAD: get_Id,
                CT_STORAGE: get_P_S_Ids,
                CT_ASSIGNED: get_P_S_DS_Ids,
                CT_INUSE: get_P_S_DS_Ids
            },
            Service: {
                CT_STORAGE: get_Id,
                CT_ASSIGNED: get_S_DS_Ids,
                CT_INUSE: get_S_DS_Ids
            },
            DeployedService: {
                CT_ASSIGNED: get_Id,
                CT_INUSE: get_Id
            }
    }
    
    
    def _getIds(obj):
        to = type(obj)
        
        if to is DeployedService:
            return to.id;
        
        if to is Service:
            return (i.id for i in obj.userServices.all())
        
        res  = ()
        if to is Provider:
            for i in obj.services.all():
                res += _getIds(i)
            return res
        return ()
    
    OT_PROVIDER, OT_SERVICE, OT_DEPLOYED = xrange(3)

    # Dict to convert objects to owner types
    # Dict for translations
    __transDict = {
        DeployedService : OT_DEPLOYED,
        Service : OT_SERVICE,
        Provider : OT_PROVIDER
    }
    
    # Titles of types
    __typeTitles = {
        CT_ASSIGNED: _('Assigned'),
        CT_INUSE: _('In use'),
        CT_LOAD: _('Load'),
        CT_STORAGE: _('Storage')
    } 
    
