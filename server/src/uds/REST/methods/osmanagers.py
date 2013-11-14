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
@osmor: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from uds.models import OSManager
from uds.core.osmanagers import factory

from uds.REST import Handler, HandlerError
from uds.REST.mixins import ModelHandlerMixin, ModelTypeHandlerMixin, ModelTableHandlerMixin

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /osm path

class OsManagers(ModelHandlerMixin, Handler):
    model = OSManager
    
    def item_as_dict(self, osm):
        type_ = osm.getType()
        return { 'id': osm.id,
                 'name': osm.name, 
                 'deployed_count': osm.deployedServices.count(),
                 'type': type_.type(),
                 'comments': osm.comments,
        }

class Types(ModelTypeHandlerMixin, Handler):
    path = 'osmanagers'
    model = OsManagers
    
    def enum_types(self):
        return factory().providers().values()

class TableInfo(ModelTableHandlerMixin, Handler):
    path = 'osmanagers'
    title =  _('Current OS Managers')
    fields = [
            { 'name': {'title': _('Name'), 'visible': True } },
            { 'comments': {'title':  _('Comments')}},
            { 'deployed_count': {'title': _('Used by'), 'type': 'numeric', 'width': '8em'}}
    ]
