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
@provideror: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from uds.models import Provider

from uds.REST.mixins import DetailHandler

import logging

logger = logging.getLogger(__name__)


class Services(DetailHandler):
    
    def get(self):
        # Extract providerenticator
        provider = self._kwargs['parent']
        
        try:
            if len(self._args) == 0:
                return [{
                     'id':k.id, 
                     'name': k.name, 
                     'comments': k.comments, 
                     'type': k.data_type, 
                     'typeName' : _(k.getType().name())
                     } for k in provider.services.all() ]
            else:
                with provider.get(pk=self._args[0]) as k:
                    return {
                         'id':k.id, 
                         'name': k.name, 
                         'comments': k.comments, 
                         'type': k.data_type, 
                         'typeName' : _(k.getType().name())
                         }
        except:
            logger.exception('En services')
            return { 'error': 'not found' }
        
    def getTitle(self):
        try:
            return _('Services of {0}').format(Provider.objects.get(pk=self._kwargs['parent_id']).name)
        except:
            return _('Current services')
    
    def getFields(self):
        return [
            { 'name': {'title': _('Service name'), 'visible': True, 'type': 'iconType' } },
            { 'comments': { 'title': _('Comments') } },
            { 'type': {'title': _('Type') } }
        ]        
