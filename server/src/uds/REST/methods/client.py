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

from uds.core.util import log
from uds.core.util.stats import events
from django.core.urlresolvers import reverse
from uds.REST import Handler
from uds.REST import RequestError
from uds.models import TicketStore
from uds.models import UserService, Transport, ServicePool, User
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.web import errors
from uds.web.views.service import getService
from uds.core.managers import cryptoManager


import datetime
import six

import logging

logger = logging.getLogger(__name__)

CLIENT_VERSION = '1.7.5'
REQUIRED_CLIENT_VERSION = '1.7.5'


# Enclosed methods under /actor path
class Client(Handler):
    '''
    Processes actor requests
    '''
    authenticated = False  # Client requests are not authenticated

    @staticmethod
    def result(result=None, error=None):
        '''
        Helper method to create a "result" set for actor response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        '''
        result = result if result is not None else ''
        res = {'result': result}
        if error is not None:
            if isinstance(error, int):
                error = errors.errorString(error)
            res['error'] = error
        return res

    def test(self):
        '''
        Executes and returns the test
        '''
        return Client.result(_('Correct'))

    def get(self):
        '''
        Processes get requests
        '''
        logger.debug("Client args for GET: {0}".format(self._args))

        if len(self._args) == 0:
            url = self._request.build_absolute_uri(reverse('ClientDownload'))
            return Client.result({
                'availableVersion': CLIENT_VERSION,
                'requiredVersion': REQUIRED_CLIENT_VERSION,
                'downloadUrl': url
            })

        try:
            ticket, scrambler = self._args
        except Exception:
            raise RequestError('Invalid request')

        try:
            data = TicketStore.get(ticket)
        except Exception:
            return Client.result(error=errors.ACCESS_DENIED)

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            res = getService(self._request, data['service'], data['transport'])
            logger.debug('Res: {}'.format(res))
            if res is not None:
                ip, userService, userServiceInstance, transport, transportInstance = res
                password = cryptoManager().xor(data['password'], scrambler).decode('utf-8')

                transportScript = transportInstance.getUDSTransportScript(userService, transport, ip, self._request.os, self._request.user, password, self._request)

                logger.debug('Script:\n{}'.format(transportScript))

                return Client.result(transportScript.encode('bz2').encode('base64'))
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=six.text_type(e))

        return Client.result(error=errors.SERVICE_NOT_READY)
