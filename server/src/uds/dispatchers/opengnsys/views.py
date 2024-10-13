# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Virtual Cable S.L.U.
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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import collections.abc
import logging

from django.http import HttpResponse, HttpRequest

from uds.REST.methods import actor_v3
from uds.core.auths import auth
from uds.models import UserService
from uds.core.util.model import process_uuid
from uds.core import types

logger = logging.getLogger(__name__)

OK = 'OK'
CONTENT_TYPE = 'text/plain'


@auth.needs_trusted_source
def opengnsys(
    request: HttpRequest,  # pylint: disable=unused-argument
    msg: str,
    token: str,
    uuid: str,
) -> HttpResponse:
    logger.debug('Received opengnsys message %s, token %s, uuid %s', msg, token, uuid)

    def _get_userservice() -> typing.Optional[UserService]:
        try:
            userservice = UserService.objects.get(uuid=process_uuid(uuid), state=types.states.State.USABLE)
            if userservice.properties.get('token') == token:
                return userservice
            logger.warning(
                'OpenGnsys: invalid token %s for userservice %s. (Ignored)',
                token,
                uuid,
            )
            # Sleep a while in case of error?
        except Exception:
            # Any exception will stop process
            logger.warning('OpenGnsys: invalid userservice %s:%s. (Ignored)', token, uuid)

        return None

    def release() -> None:
        userservice = _get_userservice()
        if userservice:
            logger.info('Released from OpenGnsys %s', userservice.friendly_name)
            userservice.properties['from_release'] = True
            userservice.release()

    def login() -> None:
        userservice = _get_userservice()
        if userservice:
            # Ignore login to cached machines...
            if userservice.cache_level != 0:
                logger.info(
                    'Ignored OpenGnsys login to %s to cached machine',
                    userservice.friendly_name,
                )
                return
            logger.debug('Processing login from OpenGnsys %s', userservice.friendly_name)
            actor_v3.Login.process_login(userservice, 'OpenGnsys')

    def logout() -> None:
        userservice = _get_userservice()
        if userservice:
            # Ignore logout to cached machines...
            if userservice.cache_level != 0:
                logger.info(
                    'Ignored OpenGnsys logout to %s to cached machine',
                    userservice.friendly_name,
                )
                return
            logger.debug('Processing logout from OpenGnsys %s', userservice.friendly_name)
            actor_v3.Logout.process_logout(userservice, 'OpenGnsys', '')  # Close all sessions

    fnc: typing.Optional[collections.abc.Callable[[], None]] = {
        'login': login,
        'logout': logout,
        'release': release,
    }.get(msg)

    if fnc:
        fnc()

    # Silently fail errors, do not notify anything (not needed anyway)
    return HttpResponse(OK, content_type=CONTENT_TYPE)
