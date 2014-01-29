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

from django.utils.translation import ugettext, ugettext_lazy as _
from uds.models import Provider, Service, UserService
from services import Services as DetailServices 
from uds.core import services

from uds.REST import NotFound, RequestError
from uds.REST.model import ModelHandler

import logging

logger = logging.getLogger(__name__)


class Providers(ModelHandler):
    model = Provider
    detail = { 'services': DetailServices }
    custom_methods = [('allservices', False), ('service', False)]
    
    save_fields = ['name', 'comments']
    
    table_title = _('Service providers')
    
    # Table info fields
    table_fields = [
            { 'name': {'title': _('Name'), 'type': 'iconType' } },
            { 'comments': {'title':  _('Comments')}},
            { 'services_count': {'title': _('Services'), 'type': 'numeric', 'width': '5em'}},
            { 'user_services_count': {'title': _('User Services'), 'type': 'numeric', 'width': '8em'}},
    ]
    
    def item_as_dict(self, provider):
        type_ = provider.getType()
        
        # Icon can have a lot of data (1-2 Kbytes), but it's not expected to have a lot of services providers, and even so, this will work fine
        offers = [{ 
            'name' : ugettext(t.name()), 
            'type' : t.type(), 
            'description' : ugettext(t.description()), 
            'icon' : t.icon().replace('\n', '') } for t in type_.getServicesTypes()]
        
        return { 'id': provider.id,
                 'name': provider.name, 
                 'services_count': provider.services.count(),
                 'user_services_count': UserService.objects.filter(deployed_service__service__provider=provider).count(),
                 'offers': offers,
                 'type': type_.type(),
                 'comments': provider.comments,
        }

    def checkDelete(self, item):
        if item.services.count() > 0:
            raise RequestError('Can\'t delete providers with services already associated')
        
    # Types related
    def enum_types(self):
        return services.factory().providers().values()
        
    # Gui related
    def getGui(self, type_):
        try:
            return self.addDefaultFields(services.factory().lookup(type_).guiDescription(), ['name', 'comments'])
        except:
            raise NotFound('type not found')
       

    def allservices(self):
        for s in Service.objects.all():
            try:
                yield DetailServices.serviceToDict(s, True)
            except:
                logger.exception('Passed service cause type is unknown')
                
    def service(self):
        try:
            return DetailServices.serviceToDict(Service.objects.get(pk=self._args[1]), True)
        except:
            raise RequestError(ugettext('Service not found'))
