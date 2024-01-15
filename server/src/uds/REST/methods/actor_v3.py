# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.
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
import enum
import functools
import logging
import time
import typing
import collections.abc

from django.conf import settings

# from uds.core import VERSION
from uds.core import consts, exceptions, osmanagers, types
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.user_service import UserServiceManager
from uds.core.util import log, security
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_datetime
from uds.core.types.states import State
from uds.models import Server, Service, TicketStore, UserService
from uds.models.service import ServiceTokenAlias
from uds.REST.utils import rest_result

from ..handlers import Handler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import services
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)

# Cache the "failed login attempts" for a given IP
cache = Cache('actorv3')


class NotifyActionType(enum.StrEnum):
    LOGIN = 'login'
    LOGOUT = 'logout'
    DATA = 'data'

    @staticmethod
    def valid_names() -> list[str]:
        return [e.value for e in NotifyActionType]


# Helpers
def fix_list_of_ids(idsList: list[str]) -> list[str]:
    """
    Params:
        idsList: List of ids to fix

    Returns:
        List of ids with both upper and lower case

    Comment:
        Due to database case sensitiveness, we need to check for both upper and lower case
    """
    return list(set([i.upper() for i in idsList] + [i.lower() for i in idsList]))


def checkBlockedIp(request: 'ExtendedHttpRequest') -> None:
    if GlobalConfig.BLOCK_ACTOR_FAILURES.as_bool() is False:
        return
    fails = cache.get(request.ip) or 0
    if fails >= consts.system.ALLOWED_FAILS:
        logger.info(
            'Access to actor from %s is blocked for %s seconds since last fail',
            request.ip,
            GlobalConfig.LOGIN_BLOCK.as_int(),
        )
        # Sleep a while to try to minimize brute force attacks somehow
        time.sleep(3)  # 3 seconds should be enough
        raise exceptions.rest.BlockAccess()


def incFailedIp(request: 'ExtendedHttpRequest') -> None:
    fails = cache.get(request.ip, 0) + 1
    cache.put(request.ip, fails, GlobalConfig.LOGIN_BLOCK.as_int())


# Decorator that clears failed counter for the IP if succeeds
def clearIfSuccess(func: collections.abc.Callable) -> collections.abc.Callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        _self = typing.cast('ActorV3Action', args[0])
        result = func(
            *args, **kwargs
        )  # If raises any exception, it will be raised and we will not clear the counter
        clearFailedIp(_self._request)  # pylint: disable=protected-access
        return result

    return wrapper


def clearFailedIp(request: 'ExtendedHttpRequest') -> None:
    cache.remove(request.ip)


class ActorV3Action(Handler):
    authenticated = False  # Actor requests are not authenticated normally
    path = 'actor/v3'

    @staticmethod
    def actor_result(result: typing.Any = None, **kwargs: typing.Any) -> dict[str, typing.Any]:
        return rest_result(result=result, **kwargs)

    @staticmethod
    def set_comms_endpoint(userService: UserService, ip: str, port: int, secret: str):
        userService.set_comms_endpoint(f'https://{ip}:{port}/actor/{secret}')

    @staticmethod
    def actorCertResult(key: str, certificate: str, password: str) -> dict[str, typing.Any]:
        return ActorV3Action.actor_result(
            {
                'private_key': key,  # To be removed on 5.0
                'key': key,
                'server_certificate': certificate,  # To be removed on 5.0
                'certificate': certificate,
                'password': password,
                'ciphers': getattr(settings, 'SECURE_CIPHERS', None),
            }
        )

    def get_userservice(self) -> UserService:
        '''
        Looks for an userService and, if not found, raises a exceptions.rest.BlockAccess request
        '''
        try:
            return UserService.objects.get(uuid=self._params['token'])
        except UserService.DoesNotExist:
            logger.error('User service not found (params: %s)', self._params)
            raise exceptions.rest.BlockAccess() from None

    def action(self) -> dict[str, typing.Any]:
        return ActorV3Action.actor_result(error='Base action invoked')

    def post(self) -> dict[str, typing.Any]:
        try:
            checkBlockedIp(self._request)
            result = self.action()
            logger.debug('Action result: %s', result)
            return result
        except (exceptions.rest.BlockAccess, KeyError):
            # For blocking attacks
            incFailedIp(self._request)
        except Exception as e:
            logger.exception('Posting %s: %s', self.__class__, e)

        raise exceptions.rest.AccessDenied('Access denied')

    # Some helpers
    def notify_service(self, action: NotifyActionType) -> None:
        try:
            # If unmanaged, use Service locator
            service: 'services.Service' = Service.objects.get(token=self._params['token']).get_instance()

            # We have a valid service, now we can make notifications

            # Build the possible ids and make initial filter to match service
            idsList = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]

            # ensure idsLists has upper and lower versions for case sensitive databases
            idsList = fix_list_of_ids(idsList)

            validId: typing.Optional[str] = service.get_valid_id(idsList)

            is_remote = self._params.get('session_type', '')[:4] in ('xrdp', 'RDP-')

            # Must be valid
            if action in (NotifyActionType.LOGIN, NotifyActionType.LOGOUT):
                if not validId:  # For login/logout, we need a valid id
                    raise Exception()
                # Notify Service that someone logged in/out

                if action == NotifyActionType.LOGIN:
                    # Try to guess if this is a remote session
                    service.process_login(validId, remote_login=is_remote)
                elif action == NotifyActionType.LOGOUT:
                    service.process_logout(validId, remote_login=is_remote)
            elif action == NotifyActionType.DATA:
                service.notify_data(validId, self._params['data'])
            else:
                raise Exception('Invalid action')

            # All right, service notified..
        except Exception as e:
            # Log error and continue
            logger.error('Error notifying service: %s (%s)', e, self._params)
            raise exceptions.rest.BlockAccess() from None


class Test(ActorV3Action):
    """
    Tests UDS Broker actor connectivity & key
    """

    name = 'test'

    def action(self) -> dict[str, typing.Any]:
        # First, try to locate an user service providing this token.
        try:
            if self._params.get('type') == consts.actor.UNMANAGED:
                Service.objects.get(token=self._params['token'])
            else:
                Server.objects.get(
                    token=self._params['token'], type=types.servers.ServerType.ACTOR
                )  # Not assigned, because only needs check
            clearFailedIp(self._request)
        except Exception:
            # Increase failed attempts
            incFailedIp(self._request)
            # And return test failed
            return ActorV3Action.actor_result('invalid token', error='invalid token')

        return ActorV3Action.actor_result('ok')


class Register(ActorV3Action):
    """
    Registers an actor
    parameters:
        - mac: mac address of the registering machine
        - ip: ip address of the registering machine
        - hostname: hostname of the registering machine
        - pre_command: command to be executed before the connection of the user is established
        - post_command: command to be executed after the actor is initialized and before set ready
        - run_once_command: comand to run just once after the actor is started. The actor will stop after this.
          The command is responsible to restart the actor.
        - log_level: log level for the actor
        - custom: Custom actor data (i.e. cetificate and comms_url for LinxApps, maybe other for other services)

    """

    authenticated = True
    needs_staff = True

    name = 'register'

    def post(self) -> dict[str, typing.Any]:
        # If already exists a token for this MAC, return it instead of creating a new one, and update the information...
        # For actors we use MAC instead of IP, because VDI normally is a dynamic IP, and we do "our best" to locate the existing actor
        # Look for a token for this mac. mac is "inside" data, so we must filter first by type and then ensure mac is inside data
        # and mac is the requested one
        found = False
        actorToken: typing.Optional[Server] = Server.objects.filter(
            type=types.servers.ServerType.ACTOR, mac=self._params['mac']
        ).first()

        # Actors does not support any SERVER API version in fact, they has their own interfaces on UserServices
        # This means that we can invoke its API from user_service, but not from server (The actor token is transformed as soon as initialized to a user service token)
        if actorToken:
            # Update parameters
            actorToken.username = self._user.pretty_name
            actorToken.ip_from = self._request.ip
            actorToken.ip = self._params['ip']
            actorToken.hostname = self._params['hostname']
            actorToken.log_level = self._params['log_level']
            actorToken.subtype = self._params.get('version', '')
            actorToken.data = {  # type: ignore
                'pre_command': self._params['pre_command'],
                'post_command': self._params['post_command'],
                'run_once_command': self._params['run_once_command'],
                'custom': self._params.get('custom', ''),
            }
            actorToken.stamp = sql_datetime()
            actorToken.save()
            logger.info('Registered actor %s', self._params)
            found = True

        if not found:
            kwargs = {
                'username': self._user.pretty_name,
                'ip_from': self._request.ip,
                'ip': self._params['ip'],
                'hostname': self._params['hostname'],
                'log_level': self._params['log_level'],
                'data': {  # type: ignore
                    'pre_command': self._params['pre_command'],
                    'post_command': self._params['post_command'],
                    'run_once_command': self._params['run_once_command'],
                    'custom': self._params.get('custom', ''),
                },
                # 'token': Server.create_token(),  # Not needed, defaults to create_token
                'type': types.servers.ServerType.ACTOR,
                'subtype': self._params.get('version', ''),
                'version': '',
                'os_type': self._params.get('os', types.os.KnownOS.UNKNOWN.os_name()),
                'mac': self._params['mac'],
                'stamp': sql_datetime(),
            }

            actorToken = Server.objects.create(**kwargs)

        return ActorV3Action.actor_result(actorToken.token)  # type: ignore  # actorToken is always assigned


class Initialize(ActorV3Action):
    """
    Information about machine action.
    Also returns the id used for the rest of the actions. (Only this one will use actor key)
    """

    name = 'initialize'

    def action(self) -> dict[str, typing.Any]:
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
            * os: Optional[dict] -> Data returned by os manager for setting up this service.
        Example:
            {
                'own_token' 'asdfasdfasdffsadfasfd'
                'unique_id': 'aa:bb:cc:dd:ee:ff'
                'os': {
                    'action': 'rename',
                    'name': 'new_name'
                }
            }
        On  error, will return Empty (None) result, and error field
        """
        # First, validate token...
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        service: typing.Optional[Service] = None
        # alias_token will contain a new master token (or same alias if not a token) to allow change on unmanaged machines.
        # Managed machines will not use this field (will return None)
        alias_token: typing.Optional[str] = None

        def initialization_result(
            own_token: typing.Optional[str],
            unique_id: typing.Optional[str],
            os: typing.Any,
            alias_token: typing.Optional[str],
        ) -> dict[str, typing.Any]:
            return ActorV3Action.actor_result(
                {
                    'own_token': own_token or alias_token,  # Compat with old actor versions, TBR on 5.0
                    'token': own_token or alias_token,  # New token, will be used from now onwards
                    'unique_id': unique_id,
                    'os': os,
                }
            )

        try:
            token = self._params['token']
            # First, try to locate an user service providing this token.
            if self._params['type'] == consts.actor.UNMANAGED:
                # First, try to locate on alias table
                if ServiceTokenAlias.objects.filter(alias=token).exists():
                    # Retrieve real service from token alias
                    service = ServiceTokenAlias.objects.get(alias=token).service
                    alias_token = token  # Store token as possible alias

                # If not found an alias, try to locate on service table
                # Not on alias token, try to locate on Service table
                if not service:
                    service = typing.cast('Service', Service.objects.get(token=token))
                    # If exists, create and alias for it
                    # Get first mac and, if not exists, get first ip
                    unique_id = self._params['id'][0].get('mac', self._params['id'][0].get('ip', ''))
                    if unique_id is None:
                        raise exceptions.rest.BlockAccess()
                    # If exists, do not create a new one (avoid creating for old 3.x actors lots of aliases...)
                    if not ServiceTokenAlias.objects.filter(service=service, unique_id=unique_id).exists():
                        alias_token = CryptoManager().random_string(40)  # fix alias with new token
                        service.aliases.create(alias=alias_token, unique_id=unique_id)
                    else:
                        # If exists, get existing one
                        alias_token = ServiceTokenAlias.objects.get(service=service, unique_id=unique_id).alias

                # Locate an userService that belongs to this service and which
                # Build the possible ids and make initial filter to match service
                idsList = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]
                dbFilter = UserService.objects.filter(deployed_service__service=service)
            else:
                # If not service provided token, use actor tokens
                if not Server.validate_token(token, types.servers.ServerType.ACTOR):
                    raise exceptions.rest.BlockAccess()
                # Build the possible ids and make initial filter to match ANY userservice with provided MAC
                idsList = [i['mac'] for i in self._params['id'][:5]]
                dbFilter = UserService.objects.all()

            # Valid actor token, now validate access allowed. That is, look for a valid mac from the ones provided.
            try:
                # ensure idsLists has upper and lower versions for case sensitive databases
                idsList = fix_list_of_ids(idsList)
                # Set full filter
                dbFilter = dbFilter.filter(
                    unique_id__in=idsList,
                    state__in=[State.USABLE, State.PREPARING],
                )

                userService: UserService = next(iter(dbFilter))
            except Exception as e:
                logger.info('Unmanaged host request: %s, %s', self._params, e)
                return initialization_result(None, None, None, alias_token)

            # Managed by UDS, get initialization data from osmanager and return it
            # Set last seen actor version
            userService.actor_version = self._params['version']
            osData: collections.abc.MutableMapping[str, typing.Any] = {}
            osManager = userService.get_osmanager_instance()
            if osManager:
                osData = osManager.actor_data(userService)

            if service and not alias_token:  # Is a service managed by UDS
                # Create a new alias for it, and save
                alias_token = CryptoManager().random_string(40)  # fix alias with new token
                service.aliases.create(alias=alias_token)

            return initialization_result(userService.uuid, userService.unique_id, osData, alias_token)
        except Service.DoesNotExist:
            raise exceptions.rest.BlockAccess() from None


class BaseReadyChange(ActorV3Action):
    """
    Records the IP change of actor
    """

    name = 'notused'  # Not really important, this is not a "leaf" class and will not be directly available

    def action(self) -> dict[str, typing.Any]:
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
        userService = self.get_userservice()
        # Stores known IP and notifies it to deployment
        userService.log_ip(self._params['ip'])
        userServiceInstance = userService.get_instance()
        userServiceInstance.set_ip(self._params['ip'])
        userService.update_data(userServiceInstance)

        # Store communications url also
        ActorV3Action.set_comms_endpoint(
            userService,
            self._params['ip'],
            int(self._params['port']),
            self._params['secret'],
        )

        if userService.os_state != State.USABLE:
            userService.setOsState(State.USABLE)
            # Notify osManager or readyness if has os manager
            osManager = userService.get_osmanager_instance()

            if osManager:
                osManager.to_ready(userService)
                UserServiceManager().notify_ready_from_os_manager(userService, '')

        # Generates a certificate and send it to client.
        privateKey, cert, password = security.create_self_signed_cert(self._params['ip'])
        # Store certificate with userService
        userService.properties['cert'] = cert
        userService.properties['priv'] = privateKey
        userService.properties['priv_passwd'] = password

        return ActorV3Action.actorCertResult(privateKey, cert, password)


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

    def action(self) -> dict[str, typing.Any]:
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
        userService = self.get_userservice()
        userService.setInUse(False)

        return result


class Version(ActorV3Action):
    """
    Notifies the version.
    Used on possible "customized" actors.
    """

    name = 'version'

    def action(self) -> dict[str, typing.Any]:
        logger.debug('Version Args: %s,  Params: %s', self._args, self._params)
        userService = self.get_userservice()
        userService.actor_version = self._params['version']
        userService.log_ip(self._params['ip'])

        return ActorV3Action.actor_result()


class Login(ActorV3Action):
    """
    Notifies user logged id
    """

    name = 'login'

    # payload received
    #   {
    #        'type': actor_type or types.MANAGED,
    #        'token': token,
    #        'username': username,
    #        'session_type': sessionType,
    #    }

    @staticmethod
    def process_login(userservice: UserService, username: str) -> typing.Optional[osmanagers.OSManager]:
        osManager: typing.Optional[osmanagers.OSManager] = userservice.get_osmanager_instance()
        if not userservice.in_use:  # If already logged in, do not add a second login (windows does this i.e.)
            osmanagers.OSManager.logged_in(userservice, username)
        return osManager

    def action(self) -> dict[str, typing.Any]:
        isManaged = self._params.get('type') != consts.actor.UNMANAGED
        src = types.connections.ConnectionSource('', '')
        deadline = max_idle = None
        session_id = ''

        logger.debug('Login Args: %s,  Params: %s', self._args, self._params)

        try:
            userservice: UserService = self.get_userservice()
            os_manager = Login.process_login(userservice, self._params.get('username') or '')

            max_idle = os_manager.max_idle() if os_manager else None

            logger.debug('Max idle: %s', max_idle)

            src = userservice.getConnectionSource()
            session_id = userservice.start_session()  # creates a session for every login requested

            if os_manager:  # For os managed services, let's check if we honor deadline
                if os_manager.ignore_deadline():
                    deadline = userservice.deployed_service.get_deadline()
                else:
                    deadline = None
            else:  # For non os manager machines, process deadline as always
                deadline = userservice.deployed_service.get_deadline()

        except (
            Exception
        ):  # If unamanaged host, lest do a bit more work looking for a service with the provided parameters...
            if isManaged:
                raise
            self.notify_service(action=NotifyActionType.LOGIN)

        return ActorV3Action.actor_result(
            {
                'ip': src.ip,
                'hostname': src.hostname,
                'dead_line': deadline,  # Kept for compat, will be removed on 5.x
                'deadline': deadline,
                'max_idle': max_idle,
                'session_id': session_id,
            }
        )


class Logout(ActorV3Action):
    """
    Notifies user logged out
    """

    name = 'logout'

    @staticmethod
    def process_logout(userservice: UserService, username: str, session_id: str) -> None:
        """
        This method is static so can be invoked from elsewhere
        """
        osManager: typing.Optional[osmanagers.OSManager] = userservice.get_osmanager_instance()

        # Close session
        # For compat, we have taken '' as "all sessions"
        userservice.end_session(session_id)

        if userservice.in_use:  # If already logged out, do not add a second logout (windows does this i.e.)
            osmanagers.OSManager.logged_out(userservice, username)
            if osManager:
                if osManager.is_removable_on_logout(userservice):
                    logger.debug('Removable on logout: %s', osManager)
                    userservice.remove()
            else:
                userservice.remove()

    def action(self) -> dict[str, typing.Any]:
        is_managed = self._params.get('type') != consts.actor.UNMANAGED

        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        try:
            userservice: UserService = self.get_userservice()  # if not exists, will raise an error
            Logout.process_logout(
                userservice,
                self._params.get('username') or '',
                self._params.get('session_id') or '',
            )
        # If unamanaged host, lets do a bit more work looking for a service with the provided parameters...
        except Exception:
            if is_managed:
                raise
            self.notify_service(NotifyActionType.LOGOUT)  # Logout notification
            # Result is that we have not processed the logout in fact, but notified the service
            return ActorV3Action.actor_result('notified')

        return ActorV3Action.actor_result('ok')


class Log(ActorV3Action):
    """
    Sends a log from the service
    """

    name = 'log'

    def action(self) -> dict[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        userservice = self.get_userservice()
        if userservice.actor_version < '4.0.0':
            # Adjust loglevel to own, we start on 10000 for OTHER, and received is 0 for OTHER
            level = log.LogLevel.from_int(int(self._params['level']) + 10000)
        else:
            level = log.LogLevel.from_int(int(self._params['level']))
        log.log(
            userservice,
            level,
            self._params['message'],
            log.LogSource.ACTOR,
        )

        return ActorV3Action.actor_result('ok')


class Ticket(ActorV3Action):
    """
    Gets an stored ticket
    """

    name = 'ticket'

    def action(self) -> dict[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)

        try:
            # Simple check that token exists
            Server.objects.get(
                token=self._params['token'], type=types.servers.ServerType.ACTOR
            )  # Not assigned, because only needs check
        except Server.DoesNotExist:
            raise exceptions.rest.BlockAccess() from None  # If too many blocks...

        try:
            return ActorV3Action.actor_result(TicketStore.get(self._params['ticket'], invalidate=True))
        except TicketStore.DoesNotExist:
            return ActorV3Action.actor_result(error='Invalid ticket')


class Unmanaged(ActorV3Action):
    name = 'unmanaged'

    def action(self) -> dict[str, typing.Any]:
        """
        unmanaged method expect a json POST with this fields:
            * id: List[dict] -> List of dictionary containing ip and mac:
            * token: str -> Valid Actor "master_token" (if invalid, will return an error).
            * secret: Secret for commsUrl for actor  (Cu
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
            service: 'services.Service' = dbService.get_instance()
        except Exception:
            return ActorV3Action.actor_result(error='Invalid token')

        # Build the possible ids and ask service if it recognizes any of it
        # If not recognized, will generate anyway the certificate, but will not be saved
        list_of_ids = [x['ip'] for x in self._params['id']] + [x['mac'] for x in self._params['id']][:10]
        valid_id: typing.Optional[str] = service.get_valid_id(list_of_ids)

        # ensure idsLists has upper and lower versions for case sensitive databases
        list_of_ids = fix_list_of_ids(list_of_ids)

        # Check if there is already an assigned user service
        # To notify it logout
        userservice: typing.Optional[UserService]
        try:
            db_filter = UserService.objects.filter(
                unique_id__in=list_of_ids,
                state__in=[State.USABLE, State.PREPARING],
            )

            userservice = next(
                iter(
                    db_filter.filter(
                        unique_id__in=list_of_ids,
                        state__in=[State.USABLE, State.PREPARING],
                    )
                )
            )
        except StopIteration:
            userservice = None

        # Try to infer the ip from the valid id (that could be an IP or a MAC)
        ip: str
        try:
            ip = next(x['ip'] for x in self._params['id'] if valid_id in (x['ip'], x['mac']))
        except StopIteration:
            ip = self._params['id'][0]['ip']  # Get first IP if no valid ip found

        # Generates a certificate and send it to client (actor).
        private_key, certificate, password = security.create_self_signed_cert(ip)

        if valid_id:
            # If id is assigned to an user service, notify "logout" to it
            if userservice:
                Logout.process_logout(userservice, 'init', '')
            else:
                # If it is not assgined to an user service, notify service
                service.notify_initialization(valid_id)

            # Store certificate, secret & port with service if validId
            service.store_id_info(
                valid_id,
                {
                    'cert': certificate,
                    'secret': self._params['secret'],
                    'port': int(self._params['port']),
                },
            )

        return ActorV3Action.actorCertResult(private_key, certificate, password)


class Notify(ActorV3Action):
    name = 'notify'

    def post(self) -> dict[str, typing.Any]:
        # Raplaces original post (non existent here)
        raise exceptions.rest.AccessDenied('Access denied')

    def get(self) -> collections.abc.MutableMapping[str, typing.Any]:
        logger.debug('Args: %s,  Params: %s', self._args, self._params)
        try:
            action = NotifyActionType(self._params['action'])
            token = self._params['token']  # pylint: disable=unused-variable  # Just to check it exists
        except Exception as e:
            # Requested login, logout or whatever
            raise exceptions.rest.RequestError('Invalid parameters') from e

        try:
            # Check block manually
            checkBlockedIp(self._request)  # pylint: disable=protected-access
            if action == NotifyActionType.LOGIN:
                Login.action(typing.cast(Login, self))
            elif action == NotifyActionType.LOGOUT:
                Logout.action(typing.cast(Logout, self))
            elif action == NotifyActionType.DATA:
                self.notify_service(action)

            return ActorV3Action.actor_result('ok')
        except UserService.DoesNotExist:
            # For blocking attacks
            incFailedIp(self._request)  # pylint: disable=protected-access

        raise exceptions.rest.AccessDenied('Access denied')
