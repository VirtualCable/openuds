# -*- coding: utf-8 -*-

#
# Copyright (c) 2015-2019 Virtual Cable S.L.
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
import datetime

import logging

from uds.REST import Handler
from uds.REST import RequestError
from uds.core.managers import userServiceManager
from uds.core.managers import cryptoManager
from uds.core.services.exceptions import ServiceNotReadyError
from uds.web.util import errors


logger = logging.getLogger(__name__)


# Enclosed methods under /connection path
class Connection(Handler):
    """
    Processes actor requests
    """
    authenticated = True  # Actor requests are not authenticated
    needs_admin = False
    needs_staff = False

    @staticmethod
    def result(result=None, error=None, errorCode=0, retryable=False):
        """
        Helper method to create a "result" set for connection response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        """
        result = result if result is not None else ''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            if isinstance(error, int):
                error = errors.errorString(error)
            if errorCode != 0:
                error += ' (code {0:04X})'.format(errorCode)
            res['error'] = error

        res['retryable'] = retryable and '1' or '0'

        return res

    def serviceList(self):
        # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
        from uds.web.util.services import getServicesData

        self._request.user = self._user

        return Connection.result(result=getServicesData(self._request))

    def connection(self, doNotCheck=False):
        idService = self._args[0]
        idTransport = self._args[1]
        try:
            ip, userService, iads, trans, itrans = userServiceManager().getService(  # pylint: disable=unused-variable
                self._user, self._request.os, self._request.ip, idService, idTransport, not doNotCheck
            )
            ci = {
                'username': '',
                'password': '',
                'domain': '',
                'protocol': 'unknown',
                'ip': ip
            }
            if doNotCheck is False:
                ci.update(itrans.getConnectionInfo(userService, self._user, 'UNKNOWN'))
            return Connection.result(result=ci)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

    def script(self):
        idService = self._args[0]
        idTransport = self._args[1]
        scrambler = self._args[2]
        hostname = self._args[3]

        try:
            res = userServiceManager().getService(self._user, self._request.os, self._request.ip, idService, idTransport)
            logger.debug('Res: %s', res)
            ip, userService, userServiceInstance, transport, transportInstance = res  # pylint: disable=unused-variable
            password = cryptoManager().symDecrpyt(self.getValue('password'), scrambler)

            userService.setConnectionSource(self._request.ip, hostname)  # Store where we are accessing from so we can notify Service

            transportScript = transportInstance.getEncodedTransportScript(userService, transport, ip, self._request.os, self._user, password, self._request)

            return Connection.result(result=transportScript)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

        return password

    def get(self):
        """
        Processes get requests
        """
        logger.debug('Connection args for GET: %s', self._args)

        if len(self._args) == 0:
            # Return list of services/transports
            return self.serviceList()
        if len(self._args) == 1:
            # Maybe we are requesting a ticket content?
            return self.getTicketContent()

        if len(self._args) == 2:
            # Return connection & validate access for service/transport
            return self.connection()

        if len(self._args) == 3:
            # /connection/idService/idTransport/skipChecking
            if self._args[2] == 'skipChecking':
                return self.connection(True)

        if len(self._args) == 4:
            # /connection/idService/idTransport/scrambler/hostname
            return self.script()

        raise RequestError('Invalid Request')
