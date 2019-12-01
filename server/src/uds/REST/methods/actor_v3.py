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
import secrets
import logging
import typing

from uds.models import (
    getSqlDatetimeAsUnix,
    getSqlDatetime,
    ActorToken,
    UserService,
    TicketStore
)

#from uds.core import VERSION
from uds.core.managers import userServiceManager
from uds.core.util import log
from uds.core.util.state import State
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig

from ..handlers import Handler, AccessDenied, RequestError

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import osmanagers

logger = logging.getLogger(__name__)

ALLOWED_FAILS = 5

class BlockAccess(Exception):
    pass

# Helpers
def checkBlockedIp(ip: str)-> None:
    cache = Cache('actorv2')
    fails = cache.get(ip) or 0
    if fails > ALLOWED_FAILS:
        logger.info('Access to actor from %s is blocked for %s seconds since last fail', ip, GlobalConfig.LOGIN_BLOCK.getInt())
        raise BlockAccess()

def incFailedIp(ip: str) -> None:
    cache = Cache('actorv2')
    fails = (cache.get(ip) or 0) + 1
    cache.put(ip, fails, GlobalConfig.LOGIN_BLOCK.getInt())

class ActorV3Action(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'actor/v2'

    @staticmethod
    def actorResult(result: typing.Any = None, error: typing.Optional[str] = None) -> typing.MutableMapping[str, typing.Any]:
        result = result or ''
        res = {'result': result, 'stamp': getSqlDatetimeAsUnix()}
        if error:
            res['error'] = error
        return res

    @staticmethod
    def setCommsUrl(userService: UserService, ip: str, secret: str):
        url = 'https://{}/actor/{}'.format(userService.getLoggedIP(), secret)
        userService.setCommsUrl(url)

    def getUserService(self) -> UserService:
        '''
        Looks for an userService and, if not found, raises a BlockAccess request
        '''
        try:
            return UserService.objects.get(uuid=self._params['token'])
        except UserService.DoesNotExist:
            raise BlockAccess()

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        return ActorV3Action.actorResult(error='Base action invoked')

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        try:
            checkBlockedIp(self._request.ip)  # pylint: disable=protected-access
            result = self.action()
            logger.debug('Action result: %s', result)
            return result
        except BlockAccess:
            # For blocking attacks
            incFailedIp(self._request.ip)  # pylint: disable=protected-access
        except Exception as e:
            logger.exception('Posting %s: %s', self.__class__, e)

        raise AccessDenied('Access denied')

class Register(ActorV3Action):
    """
    Registers an actor
    """
    authenticated = True
    name = 'register'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        actorToken: ActorToken
        try:
            # If already exists a token for this MAC, return it instead of creating a new one, and update the information...
            actorToken = ActorToken.objects.get(mac=self._params['mac'])
            # Update parameters
            actorToken.ip_from = self._request.ip
            actorToken.ip = self._params['ip']
            actorToken.hostname = self._params['hostname']
            actorToken.pre_command = self._params['pre_command']
            actorToken.post_command = self._params['post_command']
            actorToken.runonce_command = self._params['run_once_command']
            actorToken.log_level = self._params['log_level']
            actorToken.stamp = getSqlDatetime()
            actorToken.save()
        except Exception:
            actorToken = ActorToken.objects.create(
                username=self._params['username'],
                ip_from=self._request.ip,
                ip=self._params['ip'],
                hostname=self._params['hostname'],
                mac=self._params['mac'],
                pre_command=self._params['pre_command'],
                post_command=self._params['post_command'],
                runonce_command=self._params['run_once_command'],
                log_level=self._params['log_level'],
                token=secrets.token_urlsafe(36),
                stamp=getSqlDatetime()
            )
        return ActorV3Action.actorResult(actorToken.token)

class Initiialize(ActorV3Action):
    """
    Information about machine action.
    Also returns the id used for the rest of the actions. (Only this one will use actor key)
    """
    name = 'initialize'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Initialize method expect a json POST with this fields:
            * version: str -> Actor version
            * token: str -> Valid Actor Token (if invalid, will return an error)
            * id: List[dict] -> List of dictionary containing id and mac:
        Will return on field "result" a dictinary with:
            * own_token: Optional[str] -> Personal uuid for the service (That, on service, will be used from now onwards). If None, there is no own_token
            * unique_id: Optional[str] -> If not None, unique id for the service
            * max_idle: Optional[int] -> If not None, max configured Idle for the vm
            * os: Optional[dict] -> Data returned by os manager for setting up this service.
        On  error, will return Empty (None) result, and error field
        Example:
             {
                 'version': '3.0',
                 'token': 'asbdasdf',
                 'maxIdle': 99999 or None,
                 'id': [
                     {
                        'mac': 'xxxxx',
                        'ip': 'vvvvvvvv'
                     }, ...
                 ]
             }
        """
        # First, validate token...
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        try:
            ActorToken.objects.get(token=self._params['token'])  # Not assigned, because only needs check
            # Valid actor token, now validate access allowed. That is, look for a valid mac from the ones provided.
            try:
                userService: UserService = next(
                    iter(UserService.objects.filter(
                        unique_id__in=[i['mac'] for i in self._params.get('id')[:5]],
                        state__in=[State.USABLE, State.PREPARING]
                    ))
                )
            except Exception as e:
                logger.info('Unmanaged host request: %s, %s', self._params, e)
                return ActorV3Action.actorResult({
                    'own_token': None,
                    'max_idle': None,
                    'unique_id': None,
                    'os': None
                })

            # Managed by UDS, get initialization data from osmanager and return it
            # Set last seen actor version
            userService.setProperty('actor_version', self._params['version'])
            maxIdle = None
            osData: typing.MutableMapping[str, typing.Any] = {}
            osManager = userService.getOsManagerInstance()
            if osManager:
                maxIdle = osManager.maxIdle()
                logger.debug('Max idle: %s', maxIdle)
                osData = osManager.actorData(userService)

            return ActorV3Action.actorResult({
                'own_token': userService.uuid,
                'unique_id': userService.unique_id,
                'max_idle': maxIdle,
                'os': osData
            })
        except ActorToken.DoesNotExist:
            raise BlockAccess()


class ChangeIp(ActorV3Action):
    """
    Records the IP change of actor
    """
    name = 'changeip'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Changeip method expect a json POST with this fields:
            * token: str -> Valid Actor "own_token" (if invalid, will return an error).
              Currently it is the same as user service uuid, but this could change
            * secret: Secret for commsUrl for actor
            * ip: ip accesible by uds
        """
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        # Stores known IP and notifies it to deployment
        userService.logIP(self._params['ip'])
        userServiceInstance = userService.getInstance()
        userServiceInstance.setIp(self._params['ip'])
        userService.updateData(userServiceInstance)

        # Store communications url also
        ActorV3Action.setCommsUrl(userService, self._params['ip'], self._params['secret'])

        if userService.os_state != State.USABLE:
            userService.setOsState(State.USABLE)
            # Notify osManager or readyness if has os manager
            osManager = userService.getOsManagerInstance()

            if osManager:
                osManager.toReady(userService)
                userServiceManager().notifyReadyFromOsManager(userService, '')

        return ActorV3Action.actorResult('ok')


class Ready(ChangeIp):
    """
    Notifies the user service is ready
    """
    name = 'ready'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Changeip method expect a json POST with this fields:
            * token: str -> Valid Actor "own_token" (if invalid, will return an error).
              Currently it is the same as user service uuid, but this could change
            * secret: Secret for commsUrl for actor
            * ip: ip accesible by uds
        """
        result = super().action()

        # Maybe we could also set as "inUse" to false because a ready can only ocurr if an user is not logged in
        userService = self.getUserService()
        userService.setInUse(False)

        return result


class Login(ActorV3Action):
    """
    Notifies user logged id
    """
    name = 'login'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        osManager = userService.getOsManagerInstance()
        if osManager:
            osManager.loggedIn(userService, self._params.get('username') or '')

        ip, hostname = userService.getConnectionSource()
        deadLine = userService.deployed_service.getDeadline()
        return ActorV3Action.actorResult({
            'ip': ip,
            'hostname': hostname,
            'dead_line': deadLine
        })

class Logout(ActorV3Action):
    """
    Notifies user logged out
    """
    name = 'logout'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        osManager = userService.getOsManagerInstance()
        if osManager:
            osManager.loggedOut(userService, self._params.get('username') or '')
            osManager.processUnused(userService)

        return ActorV3Action.actorResult('ok')

class Log(ActorV3Action):
    """
    Sends a log from the service
    """
    name = 'log'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        log.doLog(userService, int(self._params['level']), self._params['message'], log.ACTOR)

        return ActorV3Action.actorResult('ok')

class Ticket(ActorV3Action):
    """
    Gets an stored ticket
    """
    name = 'ticket'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)

        try:
            return ActorV3Action.actorResult(TicketStore.get(self._params['ticket'], invalidate=True))
        except TicketStore.DoesNotExist:
            raise BlockAccess()  # If too many blocks...

class Notify(ActorV3Action):
    name = 'notify'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        # Raplaces original post (non existent here)
        raise AccessDenied('Access denied')

    def get(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        if 'action' not in self._params or 'token' not in self._params or self._params['action'] not in ('login', 'logout'):
            # Requested login or logout
            raise RequestError('Invalid parameters')

        try:
            # Check block manually
            checkBlockedIp(self._request.ip)  # pylint: disable=protected-access
            userService = UserService.objects.get(uuid=self._params['token'])
            # TODO: finish this
            return ActorV3Action.actorResult('ok')
        except UserService.DoesNotExist:
            # For blocking attacks
            incFailedIp(self._request.ip)  # pylint: disable=protected-access

        raise AccessDenied('Access denied')
