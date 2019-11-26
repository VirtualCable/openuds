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
    UserService
)

from uds.core import VERSION
from uds.core.util.state import State
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig

from ..handlers import Handler, AccessDenied, RequestError

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import osmanagers

logger = logging.getLogger(__name__)

ALLOWED_FAILS = 5

def actorResult(result: typing.Any = None, error: typing.Optional[str] = None) -> typing.MutableMapping[str, typing.Any]:
    result = result or ''
    res = {'result': result, 'stamp': getSqlDatetimeAsUnix()}
    if error:
        res['error'] = error
    return res

def checkBlockedIp(ip: str)-> None:
    cache = Cache('actorv2')
    fails = cache.get(ip) or 0
    if fails > ALLOWED_FAILS:
        logger.info('Access to actor from %s is blocked for %s seconds since last fail', ip, GlobalConfig.LOGIN_BLOCK.getInt())
        raise Exception()

def incFailedIp(ip: str) -> None:
    cache = Cache('actorv2')
    fails = (cache.get(ip) or 0) + 1
    cache.put(ip, fails, GlobalConfig.LOGIN_BLOCK.getInt())


# Enclosed methods under /actor path
class ActorV2(Handler):
    """
    Processes actor requests
    """
    authenticated = False  # Actor requests are not authenticated by REST api (except register)
    path = 'actor'
    name = 'v2'

    def get(self):
        """
        Processes get requests
        """
        logger.debug('Actor args for GET: %s', self._args)

        return actorResult({'version': VERSION, 'required': '3.0.0'})

class ActorV2Action(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'actor/v2'

    def get(self):
        return actorResult(VERSION)

class ActorV2Register(ActorV2Action):
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
        return actorResult(actorToken.token)

class ActorV2Initiialize(ActorV2Action):
    """
    Information about machine action.
    Also returns the id used for the rest of the actions. (Only this one will use actor key)
    """
    name = 'initialize'

    def get(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Processes get requests. Basically checks if this is a "postThoughGet" for OpenGnsys or similar
        """
        if self._args[0] == 'PostThoughGet':
            self._args = self._args[1:]  # Remove first argument
            return self.post()

        raise RequestError('Invalid request')

    def post(self) -> typing.MutableMapping[str, typing.Any]:
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
            checkBlockedIp(self._request.ip)  # Raises an exception if ip is temporarily blocked
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
                return actorResult({
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
            if userService.deployed_service.osmanager:
                osManager: 'osmanagers.OSManager' = userService.deployed_service.osmanager.getInstance()
                maxIdle = osManager.maxIdle()
                logger.debug('Max idle: %s', maxIdle)
                osData = osManager.actorData(userService)

            return actorResult({
                'own_token': userService.uuid,
                'unique_id': userService.unique_id,
                'max_idle': maxIdle,
                'os': osData
            })
        except ActorToken.DoesNotExist:
            incFailedIp(self._request.ip)  # For blocking attacks
        except Exception:
            pass

        raise AccessDenied('Access denied')

class ActorV2Login(ActorV2Action):
    """
    Notifies user logged out
    """
    name = 'login'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Logout(ActorV2Action):
    """
    Notifies user logged in
    """
    name = 'logout'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Log(ActorV2Action):
    """
    Sends a log from the service
    """
    name = 'log'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2IpChange(ActorV2Action):
    """
    Notifies an IP change
    """
    name = 'ipchange'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Ready(ActorV2Action):
    """
    Notifies the service is ready
    """
    name = 'ready'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')

class ActorV2Ticket(ActorV2Action):
    """
    Gets an stored ticket
    """
    name = 'ticket'

    def post(self):
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        return actorResult('ok')
