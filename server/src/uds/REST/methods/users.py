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

from django.utils.translation import ugettext_lazy as _
from django.utils import formats

from uds.models import User

from uds.REST.mixins import DetailHandler

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /auth path

class Users(DetailHandler):
    
    def user_as_dict(self, user):
        return {
            'id': user.id,
            'name': user.name,
            'real_name': user.real_name,
            'comments': user.comments,
            'state': user.state,
            'staff_member': user.staff_member,
            'is_admin': user.is_admin,
            'last_access': formats.date_format(user.last_access, 'DATETIME_FORMAT'),
            'parent': user.parent
        }
    
    def get(self):
        logger.debug(self._parent)
        logger.debug(self._kwargs)
        
        # Extract authenticator
        auth = self._kwargs['parent']
        
        try:
            if len(self._args) == 0:
                res = []
                for u in auth.users.all():
                    res.append(self.user_as_dict(u))
                return res
            else:
                return  self.user_as_dict(auth.get(pk=self._args[0]))
        except:
            logger.exception('En users')
            return { 'error': 'not found' }
            
        