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

from django.core.urlresolvers import reverse
from uds.REST import Handler
from uds.REST import RequestError
from uds.models import TicketStore
from uds.models import User
from uds.web import errors
from uds.core.managers import cryptoManager, userServiceManager
from uds.core.util.Config import GlobalConfig
from uds.core.services.Exceptions import ServiceNotReadyError

import six

import logging

logger = logging.getLogger(__name__)

CLIENT_VERSION = '1.9.0'
REQUIRED_CLIENT_VERSION = '1.9.0'


# Enclosed methods under /actor path
class Client(Handler):
    '''
    Processes actor requests
    '''
    authenticated = False  # Client requests are not authenticated

    @staticmethod
    def result(result=None, error=None, errorCode=0):
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
            if errorCode != 0:
                error += ' (code {0:04X})'.format(errorCode)

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

        if len(self._args) == 0:  # Gets version
            url = self._request.build_absolute_uri(reverse('ClientDownload'))
            return Client.result({
                'availableVersion': CLIENT_VERSION,
                'requiredVersion': REQUIRED_CLIENT_VERSION,
                'downloadUrl': url
            })

        if len(self._args) == 1:  # Simple test
            return Client.result(_('Correct'))

        try:
            ticket, scrambler = self._args  # If more than 2 args, got an error
            hostname = self._params['hostname']  # Or if hostname is not included...
            srcIp = self._request.ip

            # Ip is optional,
            if GlobalConfig.HONOR_CLIENT_IP_NOTIFY.getBool() is True:
                srcIp = self._params.get('ip', srcIp)

        except Exception:
            raise RequestError('Invalid request')

        logger.debug('Got Ticket: {}, scrambled: {}, Hostname: {}, Ip: {}'.format(ticket, scrambler, hostname, srcIp))

        try:
            data = TicketStore.get(ticket)
        except Exception:
            return Client.result(error=errors.ACCESS_DENIED)

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            res = userServiceManager().getService(self._request.user, self._request.ip, data['service'], data['transport'])
            logger.debug('Res: {}'.format(res))
            ip, userService, userServiceInstance, transport, transportInstance = res
            password = cryptoManager().xor(data['password'], scrambler).decode('utf-8')

            userService.setConnectionSource(srcIp, hostname)  # Store where we are accessing from so we can notify Service

            transportScript = transportInstance.getUDSTransportScript(userService, transport, ip, self._request.os, self._request.user, password, self._request)

            logger.debug('Script:\n{}'.format(transportScript))

            return Client.result(result=transportScript.encode('bz2').encode('base64'))
        except ServiceNotReadyError as e:
            return Client.result(error=errors.SERVICE_NOT_READY, errorCode=e.code)
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=six.text_type(e))

        # Will never reach this
        raise RuntimeError('Unreachable point reached!!!')
