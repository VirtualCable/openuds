# -*- coding: utf-8 -*-
#
# Copyright (c) 2018-2019 Virtual Cable S.L.
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
import logging
import typing
import collections.abc
from django.http import HttpResponseRedirect

from django.utils.translation import gettext as _

from uds.core.auths.auth import authenticate, authenticate_log_login
from uds.models import Authenticator, User
from uds.core.util.config import GlobalConfig
from uds.core.util.cache import Cache
from uds.core.util.model import processUuid
import uds.web.util.errors as errors

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports
    from uds.core.types.request import ExtendedHttpRequest
    from uds.web.forms.LoginForm import LoginForm

logger = logging.getLogger(__name__)


class LoginResult(typing.NamedTuple):
    user: typing.Optional[User] = None
    password: str = ''
    errstr: typing.Optional[str] = None
    errid: int = 0
    url: typing.Optional[str] = None


# Returns:
# (None, ErroString) if error
# (None, NumericError) if errorview redirection
# (User, password_string) if all is ok
def check_login(  # pylint: disable=too-many-branches, too-many-statements
    request: 'ExtendedHttpRequest', form: 'LoginForm', tag: typing.Optional[str] = None
) -> LoginResult:
    host = (
        request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'
    )  # Last one is a placeholder in case we can't locate host name

    # Get Authenticators limitation
    if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(False) is True:
        if not tag:
            try:
                Authenticator.objects.get(small_name=host)
                tag = host
            except Exception:
                try:
                    tag = Authenticator.objects.order_by('priority')[0].small_name  # type: ignore  # Slicing is not supported by pylance right now
                except Exception:  # There is no authenticators yet, simply allow global login to nowhere.. :-)
                    tag = None

    logger.debug('Tag: %s', tag)

    if 'uds' not in request.COOKIES:
        logger.debug('Request does not have uds cookie')
        return LoginResult(errid=errors.COOKIES_NEEDED)
    if form.is_valid():
        os = request.os
        try:
            authenticator = Authenticator.objects.get(
                uuid=processUuid(form.cleaned_data['authenticator'])
            )
        except Exception:
            authenticator = Authenticator.null()
        userName = form.cleaned_data['user']
        if GlobalConfig.LOWERCASE_USERNAME.getBool(True) is True:
            userName = userName.lower()

        cache = Cache('auth')
        cacheKey = str(authenticator.id) + userName
        tries = cache.get(cacheKey) or 0
        triesByIp = (
            (cache.get(request.ip) or 0) if GlobalConfig.LOGIN_BLOCK_IP.getBool() else 0
        )
        maxTries = GlobalConfig.MAX_LOGIN_TRIES.getInt()
        # Get instance..
        authInstance = authenticator.get_instance()
        # Check if user is locked
        if (
            authInstance.blockUserOnLoginFailures is True
            and (tries >= maxTries)
            or triesByIp >= maxTries
        ):
            authenticate_log_login(request, authenticator, userName, 'Temporarily blocked')
            return LoginResult(
                errstr=_('Too many authentication errrors. User temporarily blocked')
            )
        # check if authenticator is visible for this requests
        if authInstance.is_ip_allowed(request=request) is False:
            authenticate_log_login(
                request,
                authenticator,
                userName,
                'Access tried from an unallowed source',
            )
            return LoginResult(errstr=_('Access tried from an unallowed source'))

        password = form.cleaned_data['password'] or 'axd56adhg466jasd6q8sadñ€sáé--v'  # Random string, in fact, just a placeholder that will not be used :)
        authResult = authenticate(userName, password, authenticator, request=request)
        logger.debug('User: %s', authResult.user)

        if authResult.user is None:
            logger.debug("Invalid user %s (access denied)", userName)
            cache.put(cacheKey, tries + 1, GlobalConfig.LOGIN_BLOCK.getInt())
            cache.put(request.ip, triesByIp + 1, GlobalConfig.LOGIN_BLOCK.getInt())
            authenticate_log_login(
                request,
                authenticator,
                userName,
                'Access denied (user not allowed by UDS)',
            )
            if authResult.url:  # Redirection
                return LoginResult(url=authResult.url)
            return LoginResult(errstr=_('Access denied'))

        request.session.cycle_key()

        logger.debug('User %s has logged in', userName)
        cache.remove(cacheKey)  # Valid login, remove cached tries

        if form.cleaned_data['logouturl'] != '':
            logger.debug('The logoout url will be %s', form.cleaned_data['logouturl'])
            request.session['logouturl'] = form.cleaned_data['logouturl']
        authenticate_log_login(request, authenticator, authResult.user.name)
        return LoginResult(user=authResult.user, password=form.cleaned_data['password'])

    logger.info('Invalid form received')
    return LoginResult(errstr=_('Invalid data'))
