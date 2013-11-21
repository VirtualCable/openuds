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

#import time
from django.utils.translation import ugettext as _
from uds.core.util.State import State

from uds.models import Authenticator

from uds.REST.handlers import HandlerError
from uds.REST.mixins import DetailHandler

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /auth path

class Users(DetailHandler):
    
    def get(self):
        # Extract authenticator
        auth = self._kwargs['parent']
        
        try:
            if len(self._args) == 0:
                return list(auth.users.all().values('id','name','real_name','comments','state','staff_member','is_admin','last_access','parent'))
            else:
                return auth.get(pk=self._args[0]).values('id','name','real_name','comments','state','staff_member','is_admin','last_access','parent')
        except:
            logger.exception('En users')
            return { 'error': 'not found' }
        
    def getTitle(self):
        try:
            return _('Users of {0}').format(Authenticator.objects.get(pk=self._kwargs['parent_id']).name)
        except:
            return _('Current users')
    
    def getFields(self):
        return [
            { 'name': {'title': _('User Id'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-user text-success' } },
            { 'real_name': { 'title': _('Name') } },
            { 'comments': { 'title': _('Comments') } },
            { 'state': { 'title': _('state'), 'type': 'dict', 'dict': State.dictionary() } },
            { 'last_access': { 'title': _('Last access'), 'type': 'datetime' } },
        ]        

class Groups(DetailHandler):
    def get(self):
        # Extract authenticator
        auth = self._kwargs['parent']
        
        try:
            if len(self._args) == 0:
                return list(auth.groups.all().values('id','name', 'comments','state','is_meta'))
            else:
                return auth.get(pk=self._args[0]).values('id','name', 'comments','state','is_meta')
        except:
            logger.exception('REST groups')
            raise HandlerError('exception')
        
    def getTitle(self):
        try:
            return _('Groups of {0}').format(Authenticator.objects.get(pk=self._kwargs['parent_id']).name)
        except:
            return _('Current groups')
    
    def getFields(self):
        return [
            { 'name': {'title': _('User Id'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-group text-success' } },
            { 'comments': { 'title': _('Comments') } },
            { 'state': { 'title': _('state'), 'type': 'dict', 'dict': State.dictionary() } },
        ]        
    