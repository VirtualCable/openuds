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

from django.utils.translation import ugettext as _


from uds.models import UserService
from uds.core.util.State import State
from uds.core.util import log
from uds.core.Environment import Environment
from uds.REST.model import DetailHandler
from uds.REST import NotFound, ResponseError, RequestError
from django.db import IntegrityError

from services import Services
from osmanagers import OsManagers

import logging

logger = logging.getLogger(__name__)

class AssignedService(DetailHandler):
    
    @staticmethod
    def itemToDict(item, is_cache=False):
        val = {
            'id' : item.id,
            'id_deployed_service' : item.deployed_service_id, 
            'unique_id' : item.unique_id, 
            'friendly_name' : item.friendly_name, 
            'state' : item.state, 
            'os_state': item.os_state, 
            'state_date' : item.state_date, 
            'creation_date' : item.creation_date, 
            'revision' : item.publication and item.publication.revision or '',
        }
        
        if is_cache:
            val['cacheLevel'] = item.cache_level
        else:
            val.update({  
                'owner': item.user.manager.name + "-" + item.user.name, 
                'in_use': item.in_use, 
                'in_use_date': item.in_use_date,
                'source_host' : item.src_hostname, 
                'source_ip': item.src_ip 
            })
        return val
    
    def getItems(self, parent, item):
        # Extract provider
        try:
            if item is None:
                return [AssignedService.itemToDict(k) for k in parent.assignedUserServices().all() ]
            else:
                return parent.assignedUserServices().get(pk=item)
        except:
            logger.exception('getItems')
            self.invalidItemException()
            
    def getTitle(self, parent):
        try:
            return _('Assigned Services of {0}').format(parent.name)
        except:
            return _('Assigned services')
    
    def getFields(self, parent):
        return [
            { 'creation_date': { 'title': _('Creation date'), 'type': 'datetime' } },
            { 'revision': { 'title': _('Revision') } },
            { 'unique_id': { 'title': 'Unique ID'} },
            { 'friendly_name': {'title': _('Friendly name')} },
            { 'state': { 'title': _('State'), 'type': 'dict', 'dict': State.dictionary() } },
            { 'owner': { 'title': _('Owner') } },
        ]
            
        
class CachedService(AssignedService):
    
    def getItems(self, parent, item):
        # Extract provider
        try:
            if item is None:
                return [AssignedService.itemToDict(k, True) for k in parent.cachedUserServices().all() ]
            else:
                k = parent.cachedUserServices().get(pk=item)
                return AssignedService.itemToDict(k, True)
        except:
            logger.exception('getItems')
            self.invalidItemException()
