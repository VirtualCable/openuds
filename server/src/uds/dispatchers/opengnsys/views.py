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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import logging

from django.http import HttpResponse, HttpRequest

from uds.REST.methods import actor_v3
from uds.core.auths import auth
from uds.models import UserService
from uds.core.util.model import processUuid
from uds.core.util import states

logger = logging.getLogger(__name__)

OK = 'OK'
CONTENT_TYPE = 'text/plain'


@auth.trustedSourceRequired
def opengnsys(request: HttpRequest, msg: str, token: str, uuid: str) -> HttpResponse:
    logger.debug('Received opengnsys message %s, token %s, uuid %s', msg, token, uuid)

    def getUserService() -> typing.Optional[UserService]:
        try:
            userService = UserService.objects.get(
                uuid=processUuid(uuid), state=states.userService.USABLE
            )
            if userService.getProperty('token') == token:
                return userService
            logger.warning(
                'OpenGnsys: invalid token %s for userService %s. (Ignored)',
                token,
                uuid,
            )
            # Sleep a while in case of error?
        except Exception as e:
            # Any exception will stop process
            logger.warning(
                'OpenGnsys: invalid userService %s:%s. (Ignored)', token, uuid
            )

        return None

    def release() -> None:
        userService = getUserService()
        if userService:
            logger.info('Released from OpenGnsys %s', userService.friendly_name)
            userService.setProperty('from_release', '1')
            userService.release()

    def login() -> None:
        userService = getUserService()
        if userService:
            # Ignore login to cached machines...
            if userService.cache_level != 0:
                logger.info(
                    'Ignored OpenGnsys login to %s to cached machine',
                    userService.friendly_name,
                )
                return
            logger.debug(
                'Processing login from OpenGnsys %s', userService.friendly_name
            )
            actor_v3.Login.process_login(userService, 'OpenGnsys')

    def logout() -> None:
        userService = getUserService()
        if userService:
            # Ignore logout to cached machines...
            if userService.cache_level != 0:
                logger.info(
                    'Ignored OpenGnsys logout to %s to cached machine',
                    userService.friendly_name,
                )
                return
            logger.debug(
                'Processing logout from OpenGnsys %s', userService.friendly_name
            )
            actor_v3.Logout.process_logout(userService, 'OpenGnsys')

    fnc: typing.Optional[typing.Callable[[], None]] = {
        'login': login,
        'logout': logout,
        'release': release,
    }.get(msg)

    if fnc:
        fnc()

    # Silently fail errors, do not notify anything (not needed anyway)
    return HttpResponse(OK, content_type=CONTENT_TYPE)
