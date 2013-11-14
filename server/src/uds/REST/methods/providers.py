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
from uds.models import Provider
from uds.core import services

from uds.REST import Handler, HandlerError
from uds.REST.mixins import ModelHandlerMixin, ModelTypeHandlerMixin, ModelTableHandlerMixin

import logging

logger = logging.getLogger(__name__)


class Providers(ModelHandlerMixin, Handler):
    model = Provider
    
    def item_as_dict(self, provider):
        type_ = provider.getType()
        return { 'id': provider.id,
                 'name': provider.name, 
                 'services_count': provider.services.count(),
                 'type': type_.type(),
                 'comments': provider.comments,
        }

class Types(ModelTypeHandlerMixin, Handler):
    path = 'providers'
    
    def enum_types(self):
        return services.factory().providers().values()
    
class TableInfo(ModelTableHandlerMixin, Handler):
    path = 'providers'
    title =  _('Current service providers')
    fields = [
            { 'name': {'title': _('Name') } },
            { 'comments': {'title':  _('Comments')}},
            { 'services_count': {'title': _('Services'), 'type': 'numeric', 'width': '5em'}}
    ]
    
