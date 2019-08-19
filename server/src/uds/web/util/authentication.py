# -*- coding: utf-8 -*-
#
# Copyright (c) 2018 Virtual Cable S.L.
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

from django.utils.translation import ugettext as _

from uds.core.auths.auth import authenticate, authLogLogin
from uds.models import Authenticator
from uds.core.util.config import GlobalConfig
from uds.core.util.cache import Cache
from uds.core.util.model import processUuid

import uds.web.util.errors as errors
import logging

logger = logging.getLogger(__name__)


# Returns:
# (None, ErroString) if error
# (None, NumericError) if errorview redirection
# (User, password_string) if all if fine
def checkLogin(request, form, tag=None):
    host = request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'  # Last one is a placeholder in case we can't locate host name

    # Get Authenticators limitation
    logger.debug('Host: {0}'.format(host))
    if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(False) is True:
        if tag is None:
            try:
                Authenticator.objects.get(small_name=host)
                tag = host
            except Exception:
                try:
                    tag = Authenticator.objects.order_by('priority')[0].small_name
                except Exception:  # There is no authenticators yet, simply allow global login to nowhere.. :-)
                    tag = None

    logger.debug('Tag: {0}'.format(tag))

    if 'uds' not in request.COOKIES:
        logger.debug('Request does not have uds cookie')
        return (None, errors.COOKIES_NEEDED)
    if form.is_valid():
        os = request.os
        try:
            authenticator = Authenticator.objects.get(uuid=processUuid(form.cleaned_data['authenticator']))
        except Exception:
            authenticator = Authenticator()
        userName = form.cleaned_data['user']
        if GlobalConfig.LOWERCASE_USERNAME.getBool(True) is True:
            userName = userName.lower()

        cache = Cache('auth')
        cacheKey = str(authenticator.id) + userName
        tries = cache.get(cacheKey)
        if tries is None:
            tries = 0
        if authenticator.getInstance().blockUserOnLoginFailures is True and tries >= GlobalConfig.MAX_LOGIN_TRIES.getInt():
            authLogLogin(request, authenticator, userName, 'Temporarily blocked')
            return (None, _('Too many authentication errrors. User temporarily blocked'))
        else:
            password = form.cleaned_data['password']
            user = None
            if password == '':
                password = 'axd56adhg466jasd6q8sadñ€sáé--v'  # Random string, in fact, just a placeholder that will not be used :)
            user = authenticate(userName, password, authenticator)
            logger.debug('User: {}'.format(user))

            if user is None:
                logger.debug("Invalid user {0} (access denied)".format(userName))
                tries += 1
                cache.put(cacheKey, tries, GlobalConfig.LOGIN_BLOCK.getInt())
                authLogLogin(request, authenticator, userName, 'Access denied (user not allowed by UDS)')
                return (None, _('Access denied'))
            else:
                request.session.cycle_key()

                logger.debug('User {} has logged in'.format(userName))
                cache.remove(cacheKey)  # Valid login, remove cached tries

                # Add the "java supported" flag to session
                request.session['OS'] = os
                if form.cleaned_data['logouturl'] != '':
                    logger.debug('The logoout url will be {}'.format(form.cleaned_data['logouturl']))
                    request.session['logouturl'] = form.cleaned_data['logouturl']
                authLogLogin(request, authenticator, user.name)
                return (user, form.cleaned_data['password'])

    logger.info('Invalid form received')
    return (None, _('Invalid data'))
