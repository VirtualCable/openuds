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

from uds.REST import Handler
from uds.REST import RequestError
from uds.core.util import permissions

from uds.models import Provider, Service, Authenticator, OSManager, Transport, Network, ServicesPool
from uds.models import User, Group

import six

import logging

logger = logging.getLogger(__name__)


# Enclosed methods under /permissions path
class Permissions(Handler):
    '''
    Processes permissions requests
    '''
    needs_admin = True

    def get(self):
        '''
        Processes get requests
        '''
        logger.debug("Permissions args for GET: {0}".format(self._args))

        return ''

    def put(self):
        '''
        Processes post requests
        '''
        if len(self._args) != 4:
            raise RequestError('Invalid request')

        logger.debug('Put args: {}'.format(self._args))

        perm = {
            '0': permissions.PERMISSION_NONE,
            '1': permissions.PERMISSION_READ,
            '2': permissions.PERMISSION_ALL
        }.get(self._params.get('perm', '0'), permissions.PERMISSION_NONE)

        cls = {
            'providers': Provider,
            'service': Service
        }.get(self._args[0], None)

        if cls is None:
            raise RequestError('Invalid request')

        obj = cls.objects.get(uuid=self._args[1])

        if self._args[2] == 'users':
            user = User.objects.get(uuid=self._args[3])
            permissions.addUserPermission(user, obj, perm)
        elif self._args[2] == 'groups':
            group = Group.objects.get(uuid=self._args[3])
            permissions.addUserPermission(group, obj, perm)
        else:
            raise RequestError('Ivalid request')

        return 'ok'