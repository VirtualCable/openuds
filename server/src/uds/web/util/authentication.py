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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext as _

from uds.core import types, consts
from uds.core.auths.auth import authenticate, log_login
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig
from uds.core.util.model import process_uuid
from uds.models import Authenticator

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest
    from uds.web.forms.login_form import LoginForm

logger = logging.getLogger(__name__)


# Returns:
# (None, ErroString) if error
# (None, NumericError) if errorview redirection
# (User, password_string) if all is ok
def check_login(  # pylint: disable=too-many-branches, too-many-statements
    request: 'ExtendedHttpRequest', form: 'LoginForm'
) -> types.auth.LoginResult:

    if 'uds' not in request.COOKIES:
        logger.debug('Request does not have uds cookie')
        return types.auth.LoginResult(errid=types.errors.Error.COOKIES_NEEDED)
    if form.is_valid():
        try:
            # Get authenticator, must not be disabled
            authenticator = Authenticator.objects.exclude(state=consts.auth.DISABLED).get(
                uuid=process_uuid(form.cleaned_data['authenticator'])
            )
        except Exception:  # Don't exists an authenticator with that uuid and that is not disabled
            authenticator = Authenticator.null()
        username = form.cleaned_data['user']
        if GlobalConfig.LOWERCASE_USERNAME.as_bool(True) is True:
            username = username.lower()

        cache = Cache('auth')
        tries_cache_key = str(authenticator.id) + username
        tries = cache.get(tries_cache_key) or 0
        tries_in_this_ip = (cache.get(request.ip) or 0) if GlobalConfig.LOGIN_BLOCK_IP.as_bool() else 0
        max_tries_per_ip = GlobalConfig.MAX_LOGIN_TRIES.as_int()
        # Get instance..
        auth_instance = authenticator.get_instance()
        # Check if user is locked
        if (
            auth_instance.block_user_on_failures is True
            and (tries >= max_tries_per_ip)
            or tries_in_this_ip >= max_tries_per_ip
        ):
            log_login(request, authenticator, username, 'Temporarily blocked', as_error=True)
            return types.auth.LoginResult(errstr=_('Too many authentication errors. User temporarily blocked'))
        # check if authenticator is visible for this requests
        password = (
            form.cleaned_data['password'] or 'axd56adhg466jasd6q8sadñ€sáé--v'
        )  # Random string, in fact, just a placeholder that will not be used :)
        auth_result = authenticate(username, password, authenticator, request=request)
        logger.debug('User: %s', auth_result.user)

        if auth_result.user is None:
            logger.debug("Invalid user %s (access denied)", username)
            cache.set(tries_cache_key, tries + 1, GlobalConfig.LOGIN_BLOCK.as_int())
            cache.set(request.ip, tries_in_this_ip + 1, GlobalConfig.LOGIN_BLOCK.as_int())
            log_login(
                request,
                authenticator,
                username,
                'Access denied (user not allowed by UDS)',
                as_error=True,
            )
            if auth_result.url:  # Redirection
                return types.auth.LoginResult(url=auth_result.url)
            return types.auth.LoginResult(errstr=_('Access denied'))

        request.session.cycle_key()

        logger.debug('User %s has logged in', username)
        cache.remove(tries_cache_key)  # Valid login, remove cached tries

        if form.cleaned_data['logouturl'] != '':
            logger.debug('The logoout url will be %s', form.cleaned_data['logouturl'])
            request.session['logouturl'] = form.cleaned_data['logouturl']
        log_login(request, authenticator, auth_result.user.name)
        return types.auth.LoginResult(user=auth_result.user, password=form.cleaned_data['password'])

    logger.info('Invalid form received')
    return types.auth.LoginResult(errstr=_('Invalid data'))
