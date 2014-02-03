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

from django.utils.translation import ugettext as _


from uds.models import DeployedService, OSManager, Service
from uds.core.util.State import State
from uds.core.util import log
from uds.REST.model import ModelHandler
from django.utils.translation import ugettext
from uds.REST import RequestError, ResponseError
from uds.core.ui.UserInterface import gui
from user_services import AssignedService, CachedService, Groups, Transports, Publications

import logging

logger = logging.getLogger(__name__)

class ServicesPools(ModelHandler):
    model = DeployedService
    detail = { 
        'services': AssignedService, 
        'cache': CachedService,
        'groups':  Groups,
        'transports': Transports,
        'publications': Publications,
    }

    save_fields = ['name', 'comments', 'service_id', 'osmanager_id', 'initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs']

    table_title =  _('Deployed services')
    table_fields = [
            { 'name': {'title': _('Name') } },
            { 'parent': {'title': _('Parent Service') } }, # Will process this field on client in fact, not sent by server
            { 'state': { 'title': _('state'), 'type': 'dict', 'dict': State.dictionary() } },
            { 'comments': {'title':  _('Comments')}},
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = { 'field': 'state', 'prefix': 'row-state-' }
    
    def item_as_dict(self, item):
        val = { 'id': item.id,
            'name': item.name, 
            'comments': item.comments,
            'state' : item.state,
            'service_id': item.service_id,
            'initial_srvs' : item.initial_srvs, 
            'cache_l1_srvs' : item.cache_l1_srvs,
            'cache_l2_srvs' : item.cache_l2_srvs, 
            'max_srvs' : item.max_srvs,
            'user_services_count': item.userServices.count(),
            'restrained': item.isRestrained(),
        }
        
        if item.osmanager is not None:
            val['osmanager_id'] = item.osmanager.id

        return val
        
    # Gui related
    def getGui(self, type_):
        if OSManager.objects.count() < 1: # No os managers, can't create db
            raise ResponseError(ugettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise ResponseError(ugettext('Create at least a service before creating a new service pool'))
        
        g = self.addDefaultFields([], ['name', 'comments'])
        
        for f in [{
                     'name': 'service_id',
                     'values': [gui.choiceItem(-1, '')] + [ gui.choiceItem(v.id, v.name) for v in Service.objects.all() ],
                     'label': ugettext('Base service'),
                     'tooltip': ugettext('Service used as base of this service pool'),
                     'type': gui.InputField.CHOICE_TYPE,
                     'rdonly' : True,
                     'order': 100, # At end
                  },{
                     'name': 'osmanager_id',
                     'values': [gui.choiceItem(-1, '')] + [ gui.choiceItem(v.id, v.name) for v in OSManager.objects.all() ],
                     'label': ugettext('OS Manager'),
                     'tooltip': ugettext('OS Manager used as base of this service pool'),
                     'type': gui.InputField.CHOICE_TYPE,
                     'rdonly' : True,
                     'order': 101, # At end
                  },{
                       'name': 'initial_srvs',
                       'value': '0',
                       'label': ugettext('Initial available services'),
                       'tooltip': ugettext('Services created initially for this service pool'),
                       'type': gui.InputField.NUMERIC_TYPE,
                       'order': 102, # At end
                  },{
                       'name': 'cache_l1_srvs',
                       'value': '0',
                       'label': ugettext('Services to keep in cache'),
                       'tooltip': ugettext('Services keeped in cache for improved user service assignation'),
                       'type': gui.InputField.NUMERIC_TYPE,
                       'order': 103, # At end
                  },{
                       'name': 'cache_l2_srvs',
                       'value': '0',
                       'label': ugettext('Services to keep in L2 cache'),
                       'tooltip': ugettext('Services keeped in cache of level2 for improved service generation'),
                       'type': gui.InputField.NUMERIC_TYPE,
                       'order': 104, # At end
                  },{
                       'name': 'max_srvs',
                       'value': '0',
                       'label': ugettext('Maximum number of services to provide'),
                       'tooltip': ugettext('Maximum number of service (assigned and L1 cache) that can be created for this service'),
                       'type': gui.InputField.NUMERIC_TYPE,
                       'order': 105, # At end
                  }]:
            self.addField(g, f)
        
        return g
        
    def beforeSave(self, fields):
        logger.debug('Before {0}'.format(fields))
        logger.debug(self._args)
        try:
            try:
                service = Service.objects.get(pk=fields['service_id'])
                del fields['service_id']
                fields['service'] = service
            except:
                raise RequestError(ugettext('Base service does not exists anymore'))
            
            try:
                serviceType = service.getType()
                if serviceType.needsManager is True:
                    osmanager = OSManager.objects.get(pk=fields['osmanager_id'])
                    fields['osmanager'] = osmanager
                del fields['osmanager_id']
            except:
                raise RequestError(ugettext('This service requires an os manager'))
            
        except (RequestError, ResponseError):
            raise
        except Exception as e:
            raise RequestError(str(e))
        
    # Logs
    def getLogs(self, item):
        return log.getLogs(item)
    
