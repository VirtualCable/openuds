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
import datetime
import logging
import typing

from django.utils.translation import ugettext as _

from uds.REST import Handler
from uds.REST import RequestError
from uds.core.managers import cryptoManager
from uds.core.osmanagers import OSManager
from uds.core.util import config
from uds.core.util.state import State
from uds.core.util.model import processUuid
from uds.models import TicketStore
from uds.models import UserService

logger = logging.getLogger(__name__)

# Actor key, configurable in Security Section of administration interface
actorKey = config.Config.section(config.SECURITY_SECTION).value('Master Key',
                                                                cryptoManager().uuid(datetime.datetime.now()).replace('-', ''),
                                                                type=config.Config.TEXT_FIELD)

actorKey.get()

# Error codes:
ERR_INVALID_KEY = 1
ERR_HOST_NOT_MANAGED = 2
ERR_USER_SERVICE_NOT_FOUND = 3
ERR_OSMANAGER_ERROR = 4

# Constants for tickets
OWNER = 'ACTOR'
SECURE_OWNER = 'SACTOR'


# Enclosed methods under /actor path
class Actor(Handler):
    """
    Processes actor requests
    """
    authenticated = False  # Actor requests are not authenticated

    @staticmethod
    def result(result: typing.Any = None, error: typing.Optional[str] = None):
        """
        Helper method to create a "result" set for actor response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        """
        result = result or ''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error:
            res['error'] = error
        return res

    def test(self):
        """
        Executes and returns the test
        """
        return Actor.result(_('Correct'))

    def validateRequestKey(self):
        """
        Validates a request key (in "key" parameter)
        """
        # Ensures that key is first parameter
        # Here, path will be .../actor/ACTION/KEY (probably /rest/actor/KEY/...)
        # logger.debug('{} == {}'.format(self._params.get('key'), actorKey.get()))
        if self._params.get('key') != actorKey.get():
            return Actor.result(_('Invalid key'), error=ERR_INVALID_KEY)
        return None

    def getUserServiceByIds(self) -> UserService:
        """
        This will get the client from the IDs passed from parameters
        """
        logger.debug('Getting User services from ids: %s', self._params.get('id'))

        try:
            clientIds = [i.upper() for i in self._params.get('id').split(',')[:5]]
        except Exception:
            raise RequestError('Invalid request: (no id found)')

        services = UserService.objects.filter(unique_id__in=clientIds, state__in=[State.USABLE, State.PREPARING])

        return services[0] if services else None

    def getTicket(self):
        """
        Processes get requests in order to obtain a ticket content
        GET /rest/actor/ticket/[ticketId]?key=masterKey&[secure=true|1|false|0]
        """
        logger.debug('Ticket args for GET: %s', self._args)

        # secure = self._params.get('secure') in ('1', 'true')

        if len(self._args) != 2:
            raise RequestError('Invalid request')

        try:
            return Actor.result(TicketStore.get(self._args[1], invalidate=True))
        except Exception:
            return Actor.result({})

    def get(self):  # pylint: disable=too-many-return-statements
        """
        Processes get requests
        """
        logger.debug('Actor args for GET: %s', self._args)

        if not self._args:
            raise RequestError('Invalid request')

        if self._args[0] == 'PostThoughGet':
            self._args = self._args[1:]  # Remove first argument
            return self.post()

        if self._args[0] == 'ticket':
            return self.getTicket()

        if self._args[0] == 'testn':  # Test, but without master key
            return self.test()

        # if path is .../test (/rest/actor/[test|init]?key=.....&version=....&id=....)  version & ids are only used on init
        if self._args[0] in ('test', 'init'):
            v = self.validateRequestKey()
            if v is not None:
                return v
            if self._args[0] == 'test':
                return self.test()

            # Returns UID of selected Machine
            actorVersion: str = self._params.get('version', 'unknown')
            service = self.getUserServiceByIds()
            if service is None:
                logger.info('Unmanaged host request: %s', self._args)
                return Actor.result(_('Unmanaged host'), error=ERR_HOST_NOT_MANAGED)
            # Set last seen actor version
            service.setProperty('actor_version', actorVersion)
            maxIdle = None
            if service.deployed_service.osmanager is not None:
                maxIdle = service.deployed_service.osmanager.getInstance().maxIdle()
                logger.debug('Max idle: %s', maxIdle)
            return Actor.result(
                (
                    service.uuid,
                    service.unique_id,
                    0 if maxIdle is None else maxIdle
                )
            )
        raise RequestError('Invalid request')

    # Must be invoked as '/rest/actor/UUID/[message], with message data in post body
    def post(self):  # pylint: disable=too-many-branches
        """
        Processes post requests
        """
        if len(self._args) != 2:
            raise RequestError('Invalid request')

        uuid, message = self._args[0], self._args[1]
        if self._params.get('data') is not None:
            data = self._params['data']
        else:
            data = None

        # Right now, only "message" posts
        try:
            service: UserService = UserService.objects.get(uuid=processUuid(uuid))
        except Exception:
            return Actor.result(_('User service not found'), error=ERR_USER_SERVICE_NOT_FOUND)

        if message == 'notifyComms':
            logger.debug('Setting comms url to %s', data)
            service.setCommsUrl(data)
            return Actor.result('ok')
        if message == 'ssoAvailable':
            logger.debug('Setting that SSO is available')
            service.setProperty('sso_available', 1)
            return Actor.result('ok')
        if message == 'version':
            version = self._params.get('version', 'unknown')
            logger.debug('Got notified version %s', version)
            service.setProperty('actor_version', version)

        # "Cook" some messages, common to all clients, such as "log"
        if message == 'log':
            logger.debug(self._params)
            data = '\t'.join((self._params.get('message'), str(self._params.get('level', 10000))))

        osmanager = service.getInstance().osmanager()

        try:
            if osmanager is None:
                if message in ('login', 'logout'):
                    osm = OSManager(None, None)  # Dummy os manager, just for using "logging" capability
                    if message == 'login':
                        osm.loggedIn(service)
                    else:
                        osm.loggedOut(service)
                        # Mark for removal...
                        service.release()  # Release for removal
                    return 'ok'
                raise Exception('Unknown message {} for an user service without os manager'.format(message))
            res = osmanager.process(service, message, data, options={'scramble': False})
        except Exception as e:
            logger.exception("Exception processing from OS Manager")
            return Actor.result(str(e), ERR_OSMANAGER_ERROR)

        return Actor.result(res)
