# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import json
import logging
import typing

from django.utils.translation import ugettext as _

from django.urls import reverse
from uds.REST import Handler
from uds.REST import RequestError
from uds.models import TicketStore
from uds.models import User
from uds.web.util import errors
from uds.core.managers import cryptoManager, userServiceManager
from uds.core.util.config import GlobalConfig
from uds.core.services.exceptions import ServiceNotReadyError
from uds.core import VERSION as UDS_VERSION
from uds.core.util import encoders


logger = logging.getLogger(__name__)

CLIENT_VERSION = UDS_VERSION
REQUIRED_CLIENT_VERSION = '3.0.0'


# Enclosed methods under /actor path
class Client(Handler):
    """
    Processes actor requests
    """
    authenticated = False  # Client requests are not authenticated

    @staticmethod
    def result(
            result: typing.Any = None,
            error: typing.Optional[typing.Union[str, int]] = None,
            errorCode: int = 0,
            retryable: bool = False
        ) -> typing.Dict[str, typing.Any]:
        """
        Helper method to create a "result" set for actor response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :param errorCode: Code of the error to return, if error is not None
        :param retryable: If True, this operation can (and must) be retryed
        :return: A dictionary, suitable for response to Caller
        """
        result = result if result is not None else ''
        res = {'result': result}
        if error is not None:
            if isinstance(error, int):
                error = errors.errorString(error)
            error = str(error)  # Ensure error is an string
            if errorCode != 0:
                error += ' (code {0:04X})'.format(errorCode)

            res['error'] = error
            res['retryable'] = '1' if retryable else '0'

        logger.debug('Client Result: %s', res)

        return res

    def test(self) -> typing.Dict[str, typing.Any]:
        """
        Executes and returns the test
        """
        return Client.result(_('Correct'))

    def get(self):  # pylint: disable=too-many-locals
        """
        Processes get requests
        """
        logger.debug('Client args for GET: %s', self._args)

        if not self._args:  # Gets version
            return Client.result({
                'availableVersion': CLIENT_VERSION,
                'requiredVersion': REQUIRED_CLIENT_VERSION,
                'downloadUrl': self._request.build_absolute_uri(reverse('page.client-download'))
            })

        if len(self._args) == 1:  # Simple test
            return Client.result(_('Correct'))

        try:
            ticket, scrambler = self._args  # If more than 2 args, got an error.  pylint: disable=unbalanced-tuple-unpacking
            hostname = self._params['hostname']  # Or if hostname is not included...
            srcIp = self._request.ip

            # Ip is optional,
            if GlobalConfig.HONOR_CLIENT_IP_NOTIFY.getBool() is True:
                srcIp = self._params.get('ip', srcIp)

        except Exception:
            raise RequestError('Invalid request')

        logger.debug('Got Ticket: %s, scrambled: %s, Hostname: %s, Ip: %s', ticket, scrambler, hostname, srcIp)

        try:
            data = TicketStore.get(ticket)
        except Exception:
            return Client.result(error=errors.ACCESS_DENIED)

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            ip, userService, userServiceInstance, transport, transportInstance = userServiceManager().getService(self._request.user, self._request.os, self._request.ip, data['service'], data['transport'])
            logger.debug('Res: %s %s %s %s %s', ip, userService, userServiceInstance, transport, transportInstance)
            password = cryptoManager().symDecrpyt(data['password'], scrambler)

            userService.setConnectionSource(srcIp, hostname)  # Store where we are accessing from so we can notify Service

            transportScript, signature, params = transportInstance.getEncodedTransportScript(userService, transport, ip, self._request.os, self._request.user, password, self._request)

            logger.debug('Signature: %s', signature)
            logger.debug('Data:#######\n%s\n###########', params)

            return Client.result(result={
                'script': transportScript,
                'signature': signature,  # It is already on base64
                'params': encoders.encode(encoders.encode(json.dumps(params), 'bz2'), 'base64', asText=True),
            })
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            TicketStore.revalidate(ticket, 20)  # Retry will be in at most 5 seconds, so 20 is fine :)
            return Client.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=str(e))
