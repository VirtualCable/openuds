import json
import base64
import logging
import typing

import requests

if typing.TYPE_CHECKING:
    from uds.models import UserService, Proxy

logger = logging.getLogger(__name__)


def notifyPreconnect(userService: 'UserService', userName: str, protocol: str) -> None:
    '''
    Notifies a preconnect to an user service
    '''
    proxy = userService.deployed_service.proxy
    url = userService.getCommsUrl()
    ip, hostname = userService.getConnectionSource()

    if not url:
        logger.debug('No notification is made because agent does not supports notifications')
        return

    url += '/preConnect'

    try:
        data = {'user': userName, 'protocol': protocol, 'ip': ip, 'hostname': hostname}
        if proxy is not None:
            r = proxy.doProxyRequest(url=url, data=data, timeout=2)
        else:
            r = requests.post(
                url,
                data=json.dumps(data),
                headers={'content-type': 'application/json'},
                verify=False,
                timeout=2
            )
        r = json.loads(r.content)
        logger.debug('Sent pre-connection to client using %s: %s', url, r)
        # In fact we ignore result right now
    except Exception as e:
        logger.info('preConnection failed: %s. Check connection on destination machine: %s', e, url)

def checkUuid(userService: 'UserService') ->  bool:
    '''
    Checks if the uuid of the service is the same of our known uuid on DB
    '''
    proxy = userService.deployed_service.proxy

    url = userService.getCommsUrl()

    if not url:
        logger.debug('No uuid to retrieve because agent does not supports notifications')
        return True  # UUid is valid because it is not supported checking it

    version = userService.getProperty('actor_version') or ''
    # Just for 2.0 or newer, previous actors will not support this method.
    # Also externally supported agents will not support this method (as OpenGnsys)
    if '-' in version or version < '2.0.0':
        return True

    url += '/uuid'

    try:
        if proxy:
            r = proxy.doProxyRequest(url=url, timeout=5)
        else:
            r = requests.get(url, verify=False, timeout=5)

        if version >= '3.0.0':  # New type of response: {'result': uuid}
            uuid = r.json()['result']
        else:
            uuid = r.json()

        if uuid != userService.uuid:
            logger.info('The requested machine has uuid %s and the expected was %s', uuid, userService.uuid)
            return False

        logger.debug('Got uuid from machine: %s %s %s', url, uuid, userService.uuid)
        # In fact we ignore result right now
    except Exception as e:
        logger.error('Get uuid failed: %s. Check connection on destination machine: %s', e, url)

    return True

def requestScreenshot(userService: 'UserService') -> bytes:
    """
    Returns an screenshot in PNG format (bytes) or empty png if not supported
    """
    png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
    proxy = userService.deployed_service.proxy
    url = userService.getCommsUrl()

    version = userService.getProperty('actor_version') or ''

    # Just for 3.0 or newer, previous actors will not support this method.
    # Also externally supported agents will not support this method (as OpenGnsys)
    if '-' in version or version < '3.0.0':
        url = ''

    if url:
        try:
            data: typing.Dict[str, str] = {}
            if proxy is not None:
                r = proxy.doProxyRequest(url=url, data=data, timeout=2)
            else:
                r = requests.post(
                    url,
                    data=json.dumps(data),
                    headers={'content-type': 'application/json'},
                    verify=False,
                    timeout=2
                )
            png = json.loads(r.content)['result']

            # In fact we ignore result right now
        except Exception as e:
            logger.error('Get uuid failed: %s. Check connection on destination machine: %s', e, url)

    return base64.b64decode(png)


def sendScript(userService: 'UserService', script: str, forUser: bool = False) -> None:
    """
    If allowed, send script to user service
    """
    proxy = userService.deployed_service.proxy

    # logger.debug('Senging script: {}'.format(script))
    url = userService.getCommsUrl()
    if not url:
        logger.error('Can\'t connect with actor (no actor or legacy actor)')
        return

    url += '/script'

    try:
        data = {'script': script}
        if forUser:
            data['user'] = '1'  # Just must exists "user" parameter, don't mind value
        if proxy:
            r = proxy.doProxyRequest(url=url, data=data, timeout=5)
        else:
            r = requests.post(
                url,
                data=json.dumps(data),
                headers={'content-type': 'application/json'},
                verify=False,
                timeout=5
            )
        r = json.loads(r.content)
        logger.debug('Sent script to client using %s: %s', url, r)
        # In fact we ignore result right now
    except Exception as e:
        logger.error('Exception caught sending script: %s. Check connection on destination machine: %s', e, url)

    # All done

def requestLogoff(userService: 'UserService') -> None:
    """
    Ask client to logoff user
    """
    proxy = userService.deployed_service.proxy

    url = userService.getCommsUrl()
    if not url:
        logger.error('Can\'t connect with actor (no actor or legacy actor)')
        return

    url += '/logoff'

    try:
        data: typing.Dict = {}
        if proxy:
            r = proxy.doProxyRequest(url=url, data=data, timeout=5)
        else:
            r = requests.post(
                url,
                data=json.dumps(data),
                headers={'content-type': 'application/json'},
                verify=False,
                timeout=4
            )
        r = json.loads(r.content)
        logger.debug('Sent logoff to client using %s: %s', url, r)
        # In fact we ignore result right now
    except Exception:
        # logger.info('Logoff requested but service was not listening: %s', e, url)
        pass

    # All done
