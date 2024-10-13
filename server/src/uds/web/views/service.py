# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import json
import logging
import typing
import collections.abc

from django.utils.translation import gettext
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from uds import models
from uds.core import types
from uds.core.auths import auth
from uds.core.auths.auth import web_login_required, web_password
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.util import log
from uds.core.services.exceptions import ServiceNotReadyError, MaxServicesReachedError, ServiceAccessDeniedByCalendar

from uds.web.util import services
from uds.web.util.services import get_services_info_dict
from uds.web.views.main import logger

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser
    from uds.models import UserService

logger = logging.getLogger(__name__)


@web_login_required(admin=False)
def transport_own_link(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    def _response(url: str = '', percent: int = 100, error: typing.Any = '') -> typing.Dict[str, typing.Any]:
        return {'running': percent, 'url': url, 'error': str(error)}
    
    response: collections.abc.MutableMapping[str, typing.Any] = {}

    try:
        info = UserServiceManager.manager().get_user_service_info(
            request.user, request.os, request.ip, service_id, transport_id
        )
        # ip, userService, _iads, trans, itrans = res
        # This returns a response object in fact
        if info.ip:
            response = _response(
                url=info.transport.get_instance().get_link(
                    info.userservice,
                    info.transport,
                    info.ip,
                    request.os,
                    request.user,
                    web_password(request),
                    request,
                ),
            )
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        # error += ' (code {0:04X})'.format(e.code)
        response = _response(percent=e.code)
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "%s"', service_id)
        response = _response(error=types.errors.Error.MAX_SERVICES_REACHED.message)
    except ServiceAccessDeniedByCalendar:
        logger.info('Access tried to a calendar limited access pool "%s"', service_id)
        response = _response(error=types.errors.Error.SERVICE_CALENDAR_DENIED.message)
    except Exception as e:
        logger.exception('Error')
        response = _response(error=gettext('Internal error'))
        
    return HttpResponse(content=json.dumps(response), content_type='application/json')


# pylint: disable=unused-argument
@web_login_required(admin=False)
@never_cache
def user_service_enabler(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    return HttpResponse(
        json.dumps(services.enable_service(request, service_id=service_id, transport_id=transport_id)),
        content_type='application/json',
    )


def closer(request: 'ExtendedHttpRequest') -> HttpResponse:
    """Returns a page that closes itself (used by transports)"""
    return HttpResponse(
        '<html><head><script>window.close();</script></head><body></body></html>',
        content_type='text/html',
    )
    # return HttpResponse('<html><body onload="window.close()"></body></html>')


@web_login_required(admin=False)
@never_cache
def user_service_status(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> HttpResponse:
    '''
    Returns;
     'running' if not ready
     'ready' if is ready but not accesed by client
     'accessed' if ready and accesed by UDS client
     'error' if error is found (for example, intancing user service)
    Note:
    '''
    ip: typing.Union[str, None, bool]
    userservice: typing.Optional['UserService'] = None
    status = 'running'
    # If service exists (meta or not)
    if UserServiceManager.manager().is_meta_service(service_id):
        userservice = UserServiceManager.manager().locate_meta_service(user=request.user, id_metapool=service_id)
    else:
        userservice = UserServiceManager.manager().locate_user_service(
            user=request.user, id_userservice=service_id, create=False
        )
    if userservice:
        # Service exists...
        try:
            userservice_instance = userservice.get_instance()
            ip = userservice_instance.get_ip()
            userservice.log_ip(ip)
            # logger.debug('Res: %s %s %s %s %s', ip, userService, userServiceInstance, transport, transportInstance)
        except ServiceNotReadyError:
            ip = None
        except Exception:
            ip = False

        ready = 'ready'
        if userservice.properties.get('accessed_by_client', False) is True:
            ready = 'accessed'

        status = 'running' if ip is None else 'error' if ip is False else ready

    return HttpResponse(json.dumps({'status': status}), content_type='application/json')


@web_login_required(admin=False)
@never_cache
def action(request: 'ExtendedHttpRequestWithUser', service_id: str, action_string: str) -> HttpResponse:
    userservice = UserServiceManager.manager().locate_meta_service(request.user, service_id)
    if not userservice:
        userservice = UserServiceManager.manager().locate_user_service(request.user, service_id, create=False)

    response: typing.Any = None
    rebuild: bool = False
    if userservice:
        if action_string == 'release' and userservice.service_pool.allow_users_remove:
            rebuild = True
            log.log(
                userservice.service_pool,
                types.log.LogLevel.INFO,
                "Removing User Service {} as requested by {} from {}".format(
                    userservice.friendly_name, request.user.pretty_name, request.ip
                ),
                types.log.LogSource.WEB,
            )
            UserServiceManager.manager().request_logoff(userservice)
            userservice.release()
        elif (
            action_string == 'reset'
            and userservice.service_pool.allow_users_reset
            and userservice.service_pool.service.get_type().can_reset
        ):
            rebuild = True
            log.log(
                userservice.service_pool,
                types.log.LogLevel.INFO,
                "Reseting User Service {} as requested by {} from {}".format(
                    userservice.friendly_name, request.user.pretty_name, request.ip
                ),
                types.log.LogSource.WEB,
            )
            # UserServiceManager.manager().requestLogoff(userService)
            UserServiceManager.manager().reset(userservice)

    if rebuild:
        # Rebuild services data, but return only "this" service
        for v in services.get_services_info_dict(request)['services']:
            if v['id'] == service_id:
                response = v
                break

    return HttpResponse(json.dumps(response), content_type="application/json")


@never_cache
@auth.deny_non_authenticated  # web_login_required not used here because this is not a web page, but js
def services_data_json(request: types.requests.ExtendedHttpRequestWithUser) -> HttpResponse:
    return JsonResponse(get_services_info_dict(request))


@csrf_exempt
@auth.deny_non_authenticated
def update_transport_ticket(
    request: types.requests.ExtendedHttpRequestWithUser, ticket_id: str, scrambler: str
) -> HttpResponse:
    try:
        if request.method == 'POST':
            # Get request body as json
            data: dict[str, str] = json.loads(request.body)

            # Update username andd password in ticket
            username = data.get('username', None) or None  # None if not present
            password: 'str|bytes|None' = (
                data.get('password', None) or None
            )  # If password is empty, set it to None
            domain = data.get('domain', None) or None  # If empty string, set to None

            if password:
                password = CryptoManager().symmetric_encrypt(password, scrambler)

            def _is_ticket_valid(data: collections.abc.Mapping[str, typing.Any]) -> bool:
                if 'ticket-info' in data:
                    try:
                        user = models.User.objects.get(
                            uuid=typing.cast(dict[str, str], data['ticket-info']).get('user', None)
                        )
                        if request.user != user:
                            return False
                    except models.User.DoesNotExist:
                        return False

                    if username:
                        try:
                            userService = models.UserService.objects.get(
                                uuid=data['ticket-info'].get('userService', None)
                            )
                            UserServiceManager.manager().notify_preconnect(
                                userService,
                                types.connections.ConnectionData(
                                    username=username,
                                    protocol=data.get('protocol', ''),
                                    service_type=data['ticket-info'].get('service_type', ''),
                                ),
                            )
                        except models.UserService.DoesNotExist:
                            pass

                return True

            models.TicketStore.update(
                uuid=ticket_id,
                checking_fnc=_is_ticket_valid,
                username=username,
                password=password,
                domain=domain,
            )
            return HttpResponse('{"status": "OK"}', status=200, content_type='application/json')
    except Exception as e:
        # fallback to error
        logger.warning('Error updating ticket: %s', e)

    # Invalid request
    return HttpResponse('{"status": "Invalid Request"}', status=400, content_type='application/json')
