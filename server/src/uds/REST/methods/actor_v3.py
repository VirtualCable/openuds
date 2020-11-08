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
from uds.models import user

from uds.models import (
    getSqlDatetimeAsUnix,
    getSqlDatetime,
    ActorToken,
    UserService,
    Service,
    TicketStore,
)

#from uds.core import VERSION
from uds.core.managers import userServiceManager
from uds.core import osmanagers
from uds.core.util import log, certs
from uds.core.util.state import State
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig

from ..handlers import Handler, AccessDenied, RequestError

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import services

logger = logging.getLogger(__name__)

ALLOWED_FAILS = 5
UNMANAGED = 'unmanaged'  # matches the definition of UDS Actors OFC


class BlockAccess(Exception):
    pass

# Helpers


def checkBlockedIp(ip: str) -> None:
    cache = Cache('actorv3')
    fails = cache.get(ip) or 0
    if fails > ALLOWED_FAILS:
        logger.info('Access to actor from %s is blocked for %s seconds since last fail', ip, GlobalConfig.LOGIN_BLOCK.getInt())
        raise BlockAccess()


def incFailedIp(ip: str) -> None:
    cache = Cache('actorv3')
    fails = (cache.get(ip) or 0) + 1
    cache.put(ip, fails, GlobalConfig.LOGIN_BLOCK.getInt())


class ActorV3Action(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'actor/v3'

    @staticmethod
    def actorResult(result: typing.Any = None, error: typing.Optional[str] = None) -> typing.MutableMapping[str, typing.Any]:
        result = result or ''
        res = {'result': result, 'stamp': getSqlDatetimeAsUnix()}
        if error:
            res['error'] = error
        return res

    @staticmethod
    def setCommsUrl(userService: UserService, ip: str, port: int, secret: str):
        userService.setCommsUrl('https://{}:{}/actor/{}'.format(ip, port, secret))

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
        except (BlockAccess, KeyError):
            # For blocking attacks
            incFailedIp(self._request.ip)  # pylint: disable=protected-access
        except Exception as e:
            logger.exception('Posting %s: %s', self.__class__, e)

        raise AccessDenied('Access denied')


class Test(ActorV3Action):
    """
    Tests UDS Broker actor connectivity & key
    """
    name = 'test'

    def post(self) -> typing.MutableMapping[str, typing.Any]:
        # First, try to locate an user service providing this token.
        try:
            if self._params.get('type') == UNMANAGED:
                Service.objects.get(token=self._params['token'])
            else:
                ActorToken.objects.get(token=self._params['token'])  # Not assigned, because only needs check
        except Exception:
            return ActorV3Action.actorResult('invalid token')

        return ActorV3Action.actorResult('ok')


class Register(ActorV3Action):
    """
    Registers an actor
    """
    authenticated = True
    needs_staff = True

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
                username=self._user.pretty_name,
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
            * type: Actor type. (Currently "managed" or "unmanaged")
            * version: str -> Actor version
            * token: str -> Valid Actor Token (if invalid, will return an error)
            * id: List[dict] -> List of dictionary containing ip and mac:
        Example:
             {
                 'type': 'managed,
                 'version': '3.0',
                 'token': 'asbdasdf',
                 'id': [
                     {
                        'mac': 'aa:bb:cc:dd:ee:ff',
                        'ip': 'vvvvvvvv'
                     }, ...
                 ]
             }
        Will return on field "result" a dictinary with:
            * own_token: Optional[str] -> Personal uuid for the service (That, on service, will be used from now onwards). If None, there is no own_token
            * unique_id: Optional[str] -> If not None, unique id for the service (normally, mac adress of recognized interface)
            * max_idle: Optional[int] -> If not None, max configured Idle for the vm. Remember it can be a null value
            * os: Optional[dict] -> Data returned by os manager for setting up this service.
        Example:
            {
                'own_token' 'asdfasdfasdffsadfasfd'
                'unique_ids': 'aa:bb:cc:dd:ee:ff'
                'maxIdle': 34
            }
        On  error, will return Empty (None) result, and error field
        """
        # First, validate token...
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        try:
            # First, try to locate an user service providing this token.
            if self._params['type'] == UNMANAGED:
                # If unmanaged, use Service locator
                service: Service = Service.objects.get(token=self._params['token'])
                # Locate an userService that belongs to this service and which
                # Build the possible ids and make initial filter to match service
                idsList = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]
                dbFilter = UserService.objects.filter(deployed_service__service=service)
            else:
                # If not service provided token, use actor tokens
                ActorToken.objects.get(token=self._params['token'])  # Not assigned, because only needs check
                # Build the possible ids and make initial filter to match ANY userservice with provided MAC
                idsList = [i['mac'] for i in self._params['id'][:5]]
                dbFilter = UserService.objects.all()

            # Valid actor token, now validate access allowed. That is, look for a valid mac from the ones provided.
            try:
                userService: UserService = next(
                    iter(dbFilter.filter(
                        unique_id__in=idsList,
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
            osData: typing.MutableMapping[str, typing.Any] = {}
            osManager = userService.getOsManagerInstance()
            if osManager:
                osData = osManager.actorData(userService)

            return ActorV3Action.actorResult({
                'own_token': userService.uuid,
                'unique_id': userService.unique_id,
                'os': osData
            })
        except (ActorToken.DoesNotExist, Service.DoesNotExist):
            raise BlockAccess()


class BaseReadyChange(ActorV3Action):
    """
    Records the IP change of actor
    """
    name = 'notused'  # Not really important, this is not a "leaf" class and will not be directly available

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        BaseReady method expect a json POST with this fields:
            * token: str -> Valid Actor "own_token" (if invalid, will return an error).
              Currently it is the same as user service uuid, but this could change
            * secret: Secret for commsUrl for actor
            * ip: ip accesible by uds
            * port: port of the listener (normally 43910)

        This method will also regenerater the public-private key pair for client, that will be needed for the new ip

        Returns: {
            private_key: str -> Generated private key, PEM
            server_certificate: str -> Generated public key, PEM
        }
        """
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        # Stores known IP and notifies it to deployment
        userService.logIP(self._params['ip'])
        userServiceInstance = userService.getInstance()
        userServiceInstance.setIp(self._params['ip'])
        userService.updateData(userServiceInstance)

        # Store communications url also
        ActorV3Action.setCommsUrl(userService, self._params['ip'], int(self._params['port']), self._params['secret'])

        if userService.os_state != State.USABLE:
            userService.setOsState(State.USABLE)
            # Notify osManager or readyness if has os manager
            osManager = userService.getOsManagerInstance()

            if osManager:
                osManager.toReady(userService)
                userServiceManager().notifyReadyFromOsManager(userService, '')

        # Generates a certificate and send it to client.
        privateKey, cert, password = certs.selfSignedCert(self._params['ip'])
        # Store certificate with userService
        userService.setProperty('cert', cert)
        userService.setProperty('priv', privateKey)
        userService.setProperty('priv_passwd', password)

        return ActorV3Action.actorResult({'private_key': privateKey, 'server_certificate': cert, 'password': password})


class IpChange(BaseReadyChange):
    """
    Processses IP Change.
    """
    name = 'ipchange'


class Ready(BaseReadyChange):
    """
    Notifies the user service is ready
    """
    name = 'ready'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        Ready method expect a json POST with this fields:
            * token: str -> Valid Actor "own_token" (if invalid, will return an error).
              Currently it is the same as user service uuid, but this could change
            * secret: Secret for commsUrl for actor
            * ip: ip accesible by uds
            * port: port of the listener (normally 43910)

        Returns: {
            private_key: str -> Generated private key, PEM
            server_cert: str -> Generated public key, PEM
        }
        """
        result = super().action()

        # Maybe we could also set as "inUse" to false because a ready can only ocurr if an user is not logged in
        userService = self.getUserService()
        userService.setInUse(False)

        return result


class Version(ActorV3Action):
    """
    Notifies the version.
    Used on possible "customized" actors.
    """
    name = 'version'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Version Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        userService.setProperty('actor_version', self._params['version'])
        userService.logIP(self._params['ip'])

        return ActorV3Action.actorResult()

class LoginLogout(ActorV3Action):
    name = 'notused'  # Not really important, this is not a "leaf" class and will not be directly available

    def notifyService(self, login: bool):
        try:
            # If unmanaged, use Service locator
            service : 'services.Service' = Service.objects.get(token=self._params['token']).getInstance()
            # Locate an userService that belongs to this service and which
            # Build the possible ids and make initial filter to match service
            idsList = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]

            validId: typing.Optional[str] = service.getValidId(idsList)

            # Must be valid
            if not validId:
                raise Exception()

            # Check secret if is stored
            storedInfo : typing.Optional[typing.MutableMapping[str, typing.Any]] = service.recoverIdInfo(validId)
            # If no secret valid
            if not storedInfo or self._params['secret'] != storedInfo['secret']:
                raise Exception()

            # Notify Service that someone logged in/out
            if login:
                # Try to guess if this is a remote session
                is_remote = self._params.get('session_type', '')[:3] in ('xrdp', 'RDP-')
                service.processLogin(validId, remote_login=is_remote)
            else:
                service.processLogout(validId)

            # All right, service notified...
        except Exception:
            raise BlockAccess()


class Login(LoginLogout):
    """
    Notifies user logged id
    """
    name = 'login'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        isManaged = self._params.get('type') != UNMANAGED
        ip = hostname = ''
        deadLine = maxIdle = None

        logger.debug('Login Args: %s,  Params: %s', self._args, self._params)

        try:
            userService: typing.Optional[UserService] = self.getUserService()
        except Exception:  # If unamanaged host, lest do a bit more work looking for a service with the provided parameters...
            if isManaged:
                raise
            userService = None  # Skip later processing userService
            self.notifyService(login=True)

        if userService:
            osManager: typing.Optional[osmanagers.OSManager] = userService.getOsManagerInstance()
            if not userService.in_use:  # If already logged in, do not add a second login (windows does this i.e.)
                osmanagers.OSManager.loggedIn(userService, self._params.get('username') or '')

            maxIdle = osManager.maxIdle() if osManager else None

            logger.debug('Max idle: %s', maxIdle)

            ip, hostname = userService.getConnectionSource()
            deadLine = userService.deployed_service.getDeadline()

        return ActorV3Action.actorResult({
            'ip': ip,
            'hostname': hostname,
            'dead_line': deadLine,
            'max_idle': maxIdle
        })


class Logout(LoginLogout):
    """
    Notifies user logged out
    """
    name = 'logout'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        isManaged = self._params.get('type') != UNMANAGED

        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        try:
            userService: typing.Optional[UserService] = self.getUserService()
        except Exception:  # If unamanaged host, lest do a bit more work looking for a service with the provided parameters...
            if isManaged:
                raise
            userService = None  # Skip later processing userService
            self.notifyService(login=False)  # Logout notification

        if userService:
            osManager: typing.Optional[osmanagers.OSManager] = userService.getOsManagerInstance()
            if userService.in_use:  # If already logged out, do not add a second logout (windows does this i.e.)
                osmanagers.OSManager.loggedOut(userService, self._params.get('username') or '')
                if osManager:
                    if osManager.isRemovableOnLogout(userService):
                        logger.debug('Removable on logout: %s', osManager)
                        userService.remove()
                else:
                    userService.remove()

        return ActorV3Action.actorResult('ok')


class Log(ActorV3Action):
    """
    Sends a log from the service
    """
    name = 'log'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userService = self.getUserService()
        # Adjust loglevel to own, we start on 10000 for OTHER, and received is 0 for OTHER
        log.doLog(userService, int(self._params['level']) + 10000, self._params['message'], log.ACTOR)

        return ActorV3Action.actorResult('ok')


class Ticket(ActorV3Action):
    """
    Gets an stored ticket
    """
    name = 'ticket'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)

        try:
            # Simple check that token exists
            ActorToken.objects.get(token=self._params['token'])  # Not assigned, because only needs check
        except ActorToken.DoesNotExist:
            raise BlockAccess()  # If too many blocks...

        try:
            return ActorV3Action.actorResult(TicketStore.get(self._params['ticket'], invalidate=True))
        except TicketStore.DoesNotExists:
            return ActorV3Action.actorResult(error='Invalid ticket')


class Unmanaged(ActorV3Action):
    name = 'unmanaged'

    def action(self) -> typing.MutableMapping[str, typing.Any]:
        """
        unmanaged method expect a json POST with this fields:
            * id: List[dict] -> List of dictionary containing ip and mac:
            * token: str -> Valid Actor "master_token" (if invalid, will return an error).
            * secret: Secret for commsUrl for actor
            * port: port of the listener (normally 43910)

        This method will also regenerater the public-private key pair for client, that will be needed for the new ip

        Returns: {
            private_key: str -> Generated private key, PEM
            server_certificate: str -> Generated public key, PEM
        }
        """
        logger.debug('Args: %s,  Params: %s', self._args, self._params)

        try:
            dbService: Service = Service.objects.get(token=self._params['token'])
            service: 'services.Service' = dbService.getInstance()
        except Exception:
            return ActorV3Action.actorResult(error='Invalid token')

        # Build the possible ids and ask service if it recognizes any of it
        # If not recognized, will generate anyway the certificate, but will not be saved
        idsList = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]
        validId: typing.Optional[str] = service.getValidId(idsList)
        ip: str
        try:
            ip = next(x['ip'] for x in self._params['id'] if x['ip'] == validId or x['mac'] == validId)
        except StopIteration:
            ip = self._params['id'][0]['ip']  # Get first IP if no valid ip found

        # Generates a certificate and send it to client.
        privateKey, certificate, password = certs.selfSignedCert(ip)
        cert: typing.Dict[str, str] = {
            'private_key': privateKey,
            'server_certificate': certificate,
            'password': password
        }
        # Store certificate, secret & port with service if validId
        if validId:
            service.storeIdInfo(validId, {
                'cert': certificate,
                'secret': self._params['secret'],
                'port': int(self._params['port'])
            })

        return ActorV3Action.actorResult(cert)


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
            if 'action' == 'login':
                Login.action(typing.cast(Login, self))
            else:
                Logout.action(typing.cast(Logout, self))

            return ActorV3Action.actorResult('ok')
        except UserService.DoesNotExist:
            # For blocking attacks
            incFailedIp(self._request.ip)  # pylint: disable=protected-access

        raise AccessDenied('Access denied')
