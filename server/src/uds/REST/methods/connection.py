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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing

from uds.core import exceptions, types, consts
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.exceptions.services import ServiceNotReadyError
from uds.core.util.rest.tools import match_args
from uds.REST import Handler
from uds.web.util import services

logger = logging.getLogger(__name__)


# Enclosed methods under /connection path
class Connection(Handler):
    """
    Processes actor requests
    """

    min_access_role = consts.UserRole.USER

    @staticmethod
    def result(
        result: typing.Any = None,
        error: typing.Optional[typing.Union[str, int]] = None,
        error_code: int = 0,
        is_retrayable: bool = False,
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
            if error_code != 0:
                error += f' (code {error_code:04X})'
            res['error'] = error

        res['retryable'] = '1' if is_retrayable else '0'

        return res

    def service_list(self) -> dict[str, typing.Any]:
        # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
        # Ensure user is present on request, used by web views methods
        self._request.user = self._user

        return Connection.result(result=services.get_services_info_dict(self._request))

    def connection(self, id_service: str, id_transport: str, skip: str = '') -> dict[str, typing.Any]:
        skip_check = skip in ('doNotCheck', 'do_not_check', 'no_check', 'nocheck', 'skip_check')
        try:
            info = UserServiceManager.manager().get_user_service_info(  # pylint: disable=unused-variable
                self._user,
                self._request.os,
                self._request.ip,
                id_service,
                id_transport,
                not skip_check,
            )
            connection_info = {
                'username': '',
                'password': '',
                'domain': '',
                'protocol': 'unknown',
                'ip': info.ip or '',
            }
            if info.ip:  # only will be available id doNotCheck is False
                connection_info.update(
                    info.transport.get_instance()
                    .get_connection_info(info.userservice, self._user, 'UNKNOWN')
                    .as_dict()
                )
            return Connection.result(result=connection_info)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(
                error=types.errors.Error.SERVICE_IN_PREPARATION, error_code=e.code, is_retrayable=True
            )
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

    def script(self, id_service: str, id_transport: str, scrambler: str, hostname: str) -> dict[str, typing.Any]:
        try:
            info = UserServiceManager.manager().get_user_service_info(
                self._user, self._request.os, self._request.ip, id_service, id_transport
            )
            password = CryptoManager.manager().symmetric_decrypt(self.recover_value('password'), scrambler)

            info.userservice.set_connection_source(
                types.connections.ConnectionSource(self._request.ip, hostname)
            )  # Store where we are accessing from so we can notify Service

            if not info.ip:
                raise ServiceNotReadyError()

            transport_script = info.transport.get_instance().encoded_transport_script(
                info.userservice,
                info.transport,
                info.ip,
                self._request.os,
                self._user,
                password,
                self._request,
            )

            return Connection.result(result=transport_script)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(
                error=types.errors.Error.SERVICE_IN_PREPARATION, error_code=e.code, is_retrayable=True
            )
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=str(e))

    def get_ticket_content(self, ticketId: str) -> dict[str, typing.Any]:  # pylint: disable=unused-argument
        return {}

    def get_uds_link(self, id_service: str, id_transport: str) -> dict[str, typing.Any]:
        # Returns the UDS link for the user & transport
        self._request.user = self._user
        setattr(self._request, '_cryptedpass', self.session['REST']['password'])
        setattr(self._request, '_scrambler', self._request.META['HTTP_SCRAMBLER'])
        link_info = services.enable_service(self._request, service_id=id_service, transport_id=id_transport)
        if link_info['error']:
            return Connection.result(error=link_info['error'])
        return Connection.result(result=link_info['url'])

    def get(self) -> dict[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug('Connection args for GET: %s', self._args)

        def error() -> dict[str, typing.Any]:
            raise exceptions.rest.RequestError('Invalid Request')

        return match_args(
            self._args,
            error,
            ((), self.service_list),
            (('<ticketId>',), self.get_ticket_content),
            (('<idService>', '<idTransport>', 'udslink'), self.get_uds_link),
            (('<idService>', '<idTransport>', '<skip>'), self.connection),
            (('<idService>', '<idTransport>'), self.connection),
            (('<idService>', '<idTransport>', '<scrambler>', '<hostname>'), self.script),
        )
