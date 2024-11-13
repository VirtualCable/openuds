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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.urls import reverse
from django.utils.translation import gettext as _

from uds import models
from uds.core import consts, exceptions, types
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.exceptions.services import ServiceNotReadyError
from uds.core.types.log import LogLevel, LogSource
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_stamp_seconds
from uds.core.util.rest.tools import match
from uds.models import TicketStore, User
from uds.REST import Handler

logger = logging.getLogger(__name__)

CLIENT_VERSION: typing.Final[str] = consts.system.VERSION
LOG_ENABLED_DURATION: typing.Final[int] = 2 * 60 * 60 * 24  # 2 days


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
        error_code: int = 0,
        is_retrayable: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Helper method to create a "result" set for actor response

        Args:
            result: Result value to return (can be None, in which case it is converted to empty string '')
            error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
            error_code: Code of the error to return, if error is not None
            retryable: If True, this operation can (and must) be retried

        Returns:
            A dictionary, suitable for REST response
        """
        result = result if result is not None else ''
        res = {'result': result}
        if error:
            if isinstance(error, int):
                error = types.errors.Error.from_int(error).message
            # error = str(error)  # Ensures error is an string
            if error_code != 0:
                # Reformat error so it is better understood by users
                # error += ' (code {0:04X})'.format(errorCode)
                error = (
                    _('Your service is being created. Please, wait while we complete it')
                    + f' ({int(error_code)*25}%)'
                )

            res['error'] = error
            # is_retrayable is new key, but we keep retryable for compatibility
            res['is_retryable'] = res['retryable'] = '1' if is_retrayable else '0'

        logger.debug('Client Result: %s', res)

        return res

    def test(self) -> dict[str, typing.Any]:
        """
        Executes and returns the test
        """
        return Client.result(_('Correct'))

    def process(self, ticket: str, scrambler: str) -> dict[str, typing.Any]:
        info: typing.Optional[types.services.UserServiceInfo] = None
        hostname = self._params.get('hostname', '')  # Or if hostname is not included...
        version = self._params.get('version', '0.0.0')
        src_ip = self._request.ip

        if version < consts.system.VERSION_REQUIRED_CLIENT:
            return Client.result(error='Client version not supported.\n Please, upgrade it.')

        # Ip is optional,
        if GlobalConfig.HONOR_CLIENT_IP_NOTIFY.as_bool() is True:
            src_ip = self._params.get('ip', src_ip)

        logger.debug(
            'Got Ticket: %s, scrambled: %s, Hostname: %s, Ip: %s',
            ticket,
            scrambler,
            hostname,
            src_ip,
        )

        try:
            data: dict[str, typing.Any] = TicketStore.get(ticket)
        except TicketStore.InvalidTicket:
            return Client.result(error=types.errors.Error.ACCESS_DENIED)

        self._request.user = User.objects.get(uuid=data['user'])

        try:
            logger.debug(data)
            info = UserServiceManager.manager().get_user_service_info(
                self._request.user,
                self._request.os,
                self._request.ip,
                data['service'],
                data['transport'],
                client_hostname=hostname,
            )
            logger.debug('Res: %s', info)
            password = CryptoManager.manager().symmetric_decrypt(data['password'], scrambler)

            # userService.setConnectionSource(srcIp, hostname)  # Store where we are accessing from so we can notify Service
            if not info.ip:
                raise ServiceNotReadyError()

            transport_script = info.transport.get_instance().encoded_transport_script(
                info.userservice,
                info.transport,
                info.ip,
                self._request.os,
                self._request.user,
                password,
                self._request,
            )

            logger.debug('Script: %s', transport_script)

            # Log is enabled if user has log_enabled property set to
            try:
                log_enabled_since_limit = sql_stamp_seconds() - LOG_ENABLED_DURATION
                log_enabled_since = self._request.user.properties.get('client_logging', log_enabled_since_limit)
                is_logging_enabled = False if log_enabled_since <= log_enabled_since_limit else True
            except Exception:
                is_logging_enabled = False
            log: dict[str, 'str|None'] = {
                'level': 'DEBUG',
                'ticket': None,
            }

            if is_logging_enabled:
                log['ticket'] = TicketStore.create(
                    {
                        'user': self._request.user.uuid,
                        'userservice': info.userservice.uuid,
                        'type': 'log',
                    },
                    # Long enough for a looong time, will be cleaned on first access
                    # Or 24 hours after creation, whatever happens first
                    validity=60 * 60 * 24,
                )

            return Client.result(
                result={
                    'script': transport_script.script,
                    'type': transport_script.script_type,
                    'signature': transport_script.signature_b64,  # It is already on base64
                    'params': transport_script.encoded_parameters,
                    'log': log,
                }
            )
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            TicketStore.revalidate(ticket, 20)  # Retry will be in at most 5 seconds, so 20 is fine :)
            return Client.result(
                error=types.errors.Error.SERVICE_IN_PREPARATION, error_code=e.code, is_retrayable=True
            )
        except Exception as e:
            logger.exception("Exception")
            return Client.result(error=str(e))

        finally:
            # ensures that we mark the service as accessed by client
            # so web interface can show can react to this
            if info and info.userservice:
                info.userservice.properties['accessed_by_client'] = True

    def post(self) -> dict[str, typing.Any]:
        """
        Processes put requests

        Currently, only "upload logs"
        """
        logger.debug('Client args for POST: %s', self._args)
        try:
            ticket, command = self._args[:2]
            try:
                data: dict[str, typing.Any] = TicketStore.get(ticket)
            except TicketStore.InvalidTicket:
                return Client.result(error=types.errors.Error.ACCESS_DENIED)

            self._request.user = User.objects.get(uuid=data['user'])

            try:
                userservice = models.UserService.objects.get(uuid=data['userservice'])
            except models.UserService.DoesNotExist:
                return Client.result(error='Service not found')

            match command:
                case 'log':
                    if data.get('type') != 'log':
                        return Client.result(error='Invalid command')

                    log: str = self._params.get('log', '')
                    # Right now, log to logger, but will be stored with user logs
                    logger.info('Client %s: %s', self._request.user.pretty_name, userservice.service_pool.name)
                    for line in log.split('\n'):
                        # Firt word is level
                        try:
                            level, message = line.split(' ', 1)
                            userservice.log(message, LogLevel.from_str(level), LogSource.CLIENT)
                            logger.info('Client %s: %s', self._request.user.pretty_name, message)
                        except Exception:
                            # If something goes wrong, log it as debug
                            pass
                case _:
                    return Client.result(error='Invalid command')

        except Exception as e:
            return Client.result(error=str(e))

        return Client.result(result='Ok')

    def get(self) -> dict[str, typing.Any]:
        """
        Processes get requests
        """
        logger.debug('Client args for GET: %s', self._args)

        def _error() -> None:
            raise exceptions.rest.RequestError('Invalid request')

        def _noargs() -> dict[str, typing.Any]:
            return Client.result(
                {
                    'availableVersion': CLIENT_VERSION,  # Compat with old clients, TB removed soon...
                    'available_version': CLIENT_VERSION,
                    'requiredVersion': consts.system.VERSION_REQUIRED_CLIENT,  # Compat with old clients, TB removed soon...
                    'required_version': consts.system.VERSION_REQUIRED_CLIENT,
                    'downloadUrl': self._request.build_absolute_uri(
                        reverse('page.client-download')
                    ),  # Compat with old clients, TB removed soon...
                    'client_link': self._request.build_absolute_uri(reverse('page.client-download')),
                }
            )

        return match(
            self._args,
            _error,  # In case of error, raises RequestError
            ((), _noargs),  # No args, return version
            (('test',), self.test),  # Test request, returns "Correct"
            (
                (
                    '<ticket>',
                    '<crambler>',
                ),
                self.process,
            ),  # Process request, needs ticket and scrambler
        )
