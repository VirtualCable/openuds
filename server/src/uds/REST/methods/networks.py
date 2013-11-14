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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _
from uds.models import Network

from uds.REST import Handler, HandlerError
from uds.REST.mixins import ModelHandlerMixin, ModelTypeHandlerMixin, ModelTableHandlerMixin, ModelFakeType

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /item path

class Networks(ModelHandlerMixin, Handler):
    model = Network
    
    def item_as_dict(self, item):
        return { 'id': item.id,
                 'name': item.name,
                 'net_string': item.net_string, 
                 'networks_count': item.transports.count(),
                 'type': 'NetworkType',
        }

class Types(ModelTypeHandlerMixin, Handler):
    path = 'networks'
    
    # Fake mathods, to yield self on enum types and get a "fake" type for Network 
    def enum_types(self):
        yield ModelFakeType('Network', 'NetworkType', 'A description of a network', '')

class TableInfo(ModelTableHandlerMixin, Handler):
    path = 'networks'
    title =  _('Current Networks')
    fields = [
            { 'name': {'title': _('Name'), 'visible': True } },
            { 'net_string': {'title':  _('Networks')}},
            { 'networks_count': {'title': _('Used by'), 'type': 'numeric', 'width': '8em'}}
    ]
