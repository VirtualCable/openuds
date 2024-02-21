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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
import collections.abc
import datetime
import logging
import typing

from uds.core import exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.services.exceptions import ServiceNotReadyError
from uds.core.types.requests import ExtendedHttpRequestWithUser
from uds.core.util.rest.tools import match
from uds.REST import Handler
from uds.web.util import services

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds import models


# Enclosed methods under /connection path
class Connection(Handler):
    """
    Processes actor requests
    """

    authenticated = True  # Actor requests are not authenticated
    needs_admin = False
    needs_staff = False

    @staticmethod
    def result(
        result: typing.Any = None,
        error: typing.Optional[typing.Union[str, int]] = None,
        errorCode: int = 0,
        retryable: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Helper method to create a "result" set for connection response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        """
        result = result if result is not None else ''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error:
            if isinstance(error, int):
                error = types.errors.Error.from_int(error).message
            error = str(error)  # Ensure error is an string
            if errorCode != 0:
                error += f' (code {errorCode:04X})'
            res['error'] = error

        res['retryable'] = '1' if retryable else '0'

        return res

    def serviceList(self) -> dict[str, typing.Any]:
        # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
        # Ensure user is present on request, used by web views methods
        self._request.user = self._user

        return Connection.result(
            result=services.get_services_info_dict(self._request)
        )

    def connection(self, idService: str, idTransport: str, skip: str = '') -> dict[str, typing.Any]:
        doNotCheck = skip in ('doNotCheck', 'do_not_check', 'no_check', 'nocheck')
        try:
            (
                ip,
                userService,
                _,  # iads,
                _,  # trans,
                itrans,
            ) = UserServiceManager().get_user_service_info(  # pylint: disable=unused-variable
                self._user,
                self._request.os,
                self._request.ip,
                idService,
                idTransport,
                not doNotCheck,
            )
            connectionInfoDict = {
                'username': '',
                'password': '',
                'domain': '',
                'protocol': 'unknown',
                'ip': ip,
            }
            if itrans:  # only will be available id doNotCheck is False
                connectionInfoDict.update(
                    itrans.get_connection_info(userService, self._user, 'UNKNOWN').as_dict()
                )
            return Connection.result(result=connectionInfoDict)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(
                error=types.errors.Error.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True
            )
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

    def script(self, idService: str, idTransport: str, scrambler: str, hostname: str) -> dict[str, typing.Any]:
        try:
            res = UserServiceManager().get_user_service_info(
                self._user, self._request.os, self._request.ip, idService, idTransport
            )
            userService: 'models.UserService'
            logger.debug('Res: %s', res)
            (
                ip,
                userService,
                _,  # userServiceInstance,
                transport,
                transportInstance,
            ) = res  # pylint: disable=unused-variable
            password = CryptoManager().symmetric_decrypt(self.recover_value('password'), scrambler)

            userService.setConnectionSource(
                types.connections.ConnectionSource(self._request.ip, hostname)
            )  # Store where we are accessing from so we can notify Service

            if not ip or not transportInstance:
                raise ServiceNotReadyError()

            transportScript = transportInstance.encoded_transport_script(
                userService,
                transport,
                ip,
                self._request.os,
                self._user,
                password,
                self._request,
            )

            return Connection.result(result=transportScript)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(error=types.errors.Error.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

    def getTicketContent(self, ticketId: str) -> dict[str, typing.Any]:  # pylint: disable=unused-argument
        return {}

    def getUdsLink(self, idService: str, idTransport: str) -> dict[str, typing.Any]:
        # Returns the UDS link for the user & transport
        self._request.user = self._user
        setattr(self._request, '_cryptedpass', self.session['REST']['password'])
        setattr(self._request, '_scrambler', self._request.META['HTTP_SCRAMBLER'])
        linkInfo = services.enable_service(self._request, idService=idService, idTransport=idTransport)
        if linkInfo['error']:
            return Connection.result(error=linkInfo['error'])
        return Connection.result(result=linkInfo['url'])

    def get(self) -> dict[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug('Connection args for GET: %s', self._args)

        def error() -> dict[str, typing.Any]:
            raise exceptions.rest.RequestError('Invalid Request')

        return match(
            self._args,
            error,
            ((), self.serviceList),
            (('<ticketId>',), self.getTicketContent),
            (('<idService>', '<idTransport>', 'udslink'), self.getUdsLink),
            (('<idService>', '<idTransport>', '<skip>'), self.connection),
            (('<idService>', '<idTransport>'), self.connection),
            (('<idService>', '<idTransport>', '<scrambler>', '<hostname>'), self.script),
        )
