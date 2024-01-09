# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import logging
import typing

from django.urls import reverse
from django.utils.translation import gettext as _

from uds.core import consts, exceptions
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.user_service import UserServiceManager
from uds.core.services.exceptions import ServiceNotReadyError
from uds.core.util.config import GlobalConfig
from uds.core.util.rest.tools import match
from uds.models import TicketStore, User
from uds.REST import Handler
from uds.web.util import errors

if typing.TYPE_CHECKING:
    from uds.models import UserService

logger = logging.getLogger(__name__)

CLIENT_VERSION = consts.system.VERSION


# Enclosed methods under /client path
class Client(Handler):
    """
    Processes Client requests
    """

    authenticated = False  # Client requests are not authenticated

    @staticmethod
    def result(
        result: typing.Any = None,
        error: typing.Optional[typing.Union[str, int]] = None,
        errorCode: int = 0,
        retryable: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Helper method to create a "result" set for actor response

        Args:
            result: Result value to return (can be None, in which case it is converted to empty string '')
            error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
            errorCode: Code of the error to return, if error is not None
            retryable: If True, this operation can (and must) be retried

        Returns:
            A dictionary, suitable for REST response
        """
        result = result if result is not None else ''
        res = {'result': result}
        if error:
            if isinstance(error, int):
                error = errors.errorString(error)
            error = str(error)  # Ensures error is an string
            if errorCode != 0:
                # Reformat error so it is better understood by users
                # error += ' (code {0:04X})'.format(errorCode)
                error = (
                    _('Your service is being created. Please, wait while we complete it')
                    + f' ({int(errorCode)*25}%)'
                )

            res['error'] = error
            res['retryable'] = '1' if retryable else '0'

        logger.debug('Client Result: %s', res)

        return res

    def test(self) -> dict[str, typing.Any]:
        """
        Executes and returns the test
        """
        return Client.result(_('Correct'))

    def process(self, ticket: str, scrambler: str) -> dict[str, typing.Any]:
        userService: typing.Optional['UserService'] = None
        hostname = self._params.get('hostname', '')  # Or if hostname is not included...
        version = self._params.get('version', '0.0.0')
        srcIp = self._request.ip

        if version < consts.system.REQUIRED_CLIENT_VERSION:
            return Client.result(error='Client version not supported.\n Please, upgrade it.')

        # Ip is optional,
        if GlobalConfig.HONOR_CLIENT_IP_NOTIFY.getBool() is True:
            srcIp = self._params.get('ip', srcIp)

        logger.debug(
            'Got Ticket: %s, scrambled: %s, Hostname: %s, Ip: %s',
            ticket,
            scrambler,
            hostname,
            srcIp,
        )

        try:
            data = TicketStore.get(ticket)
        except TicketStore.InvalidTicket:
            return Client.result(error=errors.ACCESS_DENIED)

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            (
                ip,
                userService,
                userServiceInstance,
                transport,
                transportInstance,
            ) = UserServiceManager().get_user_service_info(
                self._request.user,
                self._request.os,
                self._request.ip,
                data['service'],
                data['transport'],
                client_hostname=hostname,
            )
            logger.debug(
                'Res: %s %s %s %s %s',
                ip,
                userService,
                userServiceInstance,
                transport,
                transportInstance,
            )
            password = CryptoManager().symmetric_decrypt(data['password'], scrambler)

            # userService.setConnectionSource(srcIp, hostname)  # Store where we are accessing from so we can notify Service
            if not ip:
                raise ServiceNotReadyError()

            # This should never happen, but it's here just in case
            if not transportInstance:
                raise Exception('No transport instance!!!')

            transport_script = transportInstance.encoded_transport_script(
                userService,
                transport,
                ip,
                self._request.os,
                self._request.user,
                password,
                self._request,
            )

            logger.debug('Script: %s', transport_script)

            return Client.result(
                result={
                    'script': transport_script.script,
                    'type': transport_script.script_type,
                    'signature': transport_script.signature_b64,  # It is already on base64
                    'params': transport_script.encoded_parameters,
                }
            )
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            TicketStore.revalidate(ticket, 20)  # Retry will be in at most 5 seconds, so 20 is fine :)
            return Client.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=str(e))

        finally:
            # ensures that we mark the service as accessed by client
            # so web interface can show can react to this
            if userService:
                userService.properties['accessed_by_client'] = True

    def get(self) -> dict[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug('Client args for GET: %s', self._args)

        def error() -> None:
            raise exceptions.rest.RequestError('Invalid request')

        def noargs() -> dict[str, typing.Any]:
            return Client.result(
                {
                    'availableVersion': CLIENT_VERSION,
                    'requiredVersion': consts.system.REQUIRED_CLIENT_VERSION,
                    'downloadUrl': self._request.build_absolute_uri(reverse('page.client-download')),
                }
            )

        return match(
            self._args,
            error,  # In case of error, raises RequestError
            ((), noargs),  # No args, return version
            (('test',), self.test),  # Test request, returns "Correct"
            (
                (
                    '<ticket>',
                    '<crambler>',
                ),
                self.process,
            ),  # Process request, needs ticket and scrambler
        )
