import os
import json
import base64
import tempfile
import logging
import typing

import requests

if typing.TYPE_CHECKING:
    from uds.models import UserService, Proxy

logger = logging.getLogger(__name__)

TIMEOUT = 2

class NoActorComms(Exception):
    pass

class OldActorVersion(NoActorComms):
    pass

def _requestActor(
        userService: 'UserService',
        method: str,
        data: typing.Optional[typing.MutableMapping[str, typing.Any]] = None,
        minVersion: typing.Optional[str] = None
    ) -> typing.Any:
    """
    Makes a request to actor using "method"
    if data is None, request is done using GET, else POST
    if no communications url is provided or no min version, raises a "NoActorComms" exception (or OldActorVersion, derived from NoActorComms)
    Returns request response value interpreted as json
    """
    url = userService.getCommsUrl()
    if not url:
        logger.warning('No notification is made because agent does not supports notifications: %s', userService.friendly_name)
        raise NoActorComms('No notification urls for {}'.format(userService.friendly_name))

    minVersion = minVersion or '2.0.0'
    version = userService.getProperty('actor_version') or '0.0.0'
    if '-' in version or version < minVersion:
        logger.warning('Pool %s has old actors (%s)', userService.deployed_service.name, version)
        raise OldActorVersion('Old actor version {} for {}'.format(version, userService.friendly_name))

    url += '/' + method

    proxy = userService.deployed_service.proxy
    try:
        if proxy:
            r = proxy.doProxyRequest(url=url, data=data, timeout=TIMEOUT)
        else:
            verify: typing.Union[bool, str]
            # cert = userService.getProperty('cert')
            cert = ''  # Untils more tests, keep as previous....  TODO: Fix this when fully tested
            if cert:
                # Generate temp file, and delete it after
                verify = tempfile.mktemp('udscrt')
                with open(verify, 'wb') as f:
                    f.write(cert.encode())  # Save cert
            else:
                verify = False
            if data is None:
                r = requests.get(url, verify=verify, timeout=TIMEOUT)
            else:
                r = requests.post(
                    url,
                    data=json.dumps(data),
                    headers={'content-type': 'application/json'},
                    verify=verify,
                    timeout=TIMEOUT
                )
            if verify:
                try:
                    os.remove(typing.cast(str, verify))
                except Exception:
                    logger.exception('removing verify')
        js = r.json()

        if version >= '3.0.0':
            js = js['result']
        logger.debug('Requested %s to actor. Url=%s', method, url)
    except Exception as e:
        logger.warning('Request %s failed: %s. Check connection on destination machine: %s', method, e, url)
        js = None

    return js

def notifyPreconnect(userService: 'UserService', userName: str, protocol: str) -> None:
    '''
    Notifies a preconnect to an user service
    '''
    ip, hostname = userService.getConnectionSource()
    try:
        _requestActor(userService, 'preConnect', {'user': userName, 'protocol': protocol, 'ip': ip, 'hostname': hostname})
    except NoActorComms:
        pass  # If no preconnect, warning will appear on UDS log

def checkUuid(userService: 'UserService') ->  bool:
    '''
    Checks if the uuid of the service is the same of our known uuid on DB
    '''
    try:
        uuid = _requestActor(userService, 'uuid')
        if uuid != userService.uuid:
            logger.info('Machine %s do not have expected uuid %s, instead has %s', userService.friendly_name, userService.uuid, uuid)
            return False
    except NoActorComms:
        pass

    return True   # Actor does not supports checking

def requestScreenshot(userService: 'UserService') -> bytes:
    """
    Returns an screenshot in PNG format (bytes) or empty png if not supported
    """
    emptyPng = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    try:
        png = _requestActor(userService, 'screenshot', minVersion='3.0.0')  # First valid version with screenshot is 3.0
    except NoActorComms:
        png = None

    return base64.b64decode(png or emptyPng)

def sendScript(userService: 'UserService', script: str, forUser: bool = False) -> None:
    """
    If allowed, send script to user service
    """
    _requestActor(userService, 'script', data={'script': script, 'user': forUser}, minVersion='3.0.0')

def requestLogoff(userService: 'UserService') -> None:
    """
    Ask client to logoff user
    """
    _requestActor(userService, 'logout', data={})

def sendMessage(userService: 'UserService', message: str) -> None:
    """
    Sends an screen message to client
    """
    _requestActor(userService, 'message', data={'message':message})
