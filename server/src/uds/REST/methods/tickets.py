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
from uds.models import Authenticator
from django.contrib.sessions.backends.db import SessionStore


import datetime
import six

import logging

logger = logging.getLogger(__name__)


# Enclosed methods under /actor path
class Ticket(Handler):
    '''
    Processes actor requests
    '''
    needs_admin = True  # By default, staff is lower level needed

    @staticmethod
    def result(result='', error=None):
        '''
        Returns a result for a Ticket request
        '''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            res['error'] = error
        return res

    def get(self):
        '''
        Processes get requests, currently none
        '''
        logger.debug("Ticket args for GET: {0}".format(self._args))

        raise RequestError('Invalid request')

    # Must be invoked as '/rest/ticket/create, with "username", ("authId" or "authSmallName", "group" and optionally "time" (in seconds) as paramteres
    def put(self):
        '''
        Processes put requests, currently only under "create"
        '''
        if len(self._args) != 1 or self._args[1] not in ('create',):
            raise RequestError('Invalid method')

        if 'username' not in self._params or 'group' not in self._params:
            raise RequestError('Invalid parameters')

        if 'authId' not in self._params and 'authSmallName' not in self._params:
            raise RequestError('Invalid parameters (no auth)')

        try:
            authId = self._params.get('authId', None)
            authSmallName = self._params.get('authSmallName', None)

            # Will raise an exception if no auth found
            if authId is not None:
                auth = Authenticator.objects.get(uuid=authId)
            else:
                auth = Authenticator.objects.get(small_name=authSmallName)

            username = self._params['username']
            group = self._params['group']
            time = int(self._params.get('time', 60))
            # Try to get auth, or raise an exception if auth is not found

        except Exception as e:
            return Ticket.result(error=six.text_type(e))
        except Authenticator.DoesNotExist:
            return Ticket.result(error='Authenticator does not exits')

        store = SessionStore()
        store.set_expiry(time)
        store['username'] = username
        store['group'] = group
        store['auth'] = auth.uuid
        store.save()

        return Ticket.result(store.session_key)
