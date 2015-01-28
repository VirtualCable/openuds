# -*- coding: utf-8 -*-
#
# Copyright (c) 2012 Virtual Cable S.L.
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
from __future__ import unicode_literals

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.urlresolvers import reverse

from uds.core.auths.auth import webLogin, authenticate, authLogLogin, authLogLogout, getUDSCookie, webLoginRequired, webLogout
from uds.models import Authenticator
from uds.web.forms.LoginForm import LoginForm
from uds.core.util.Config import GlobalConfig
from uds.core.util.Cache import Cache
from uds.core.util import OsDetector
from uds.core.ui import theme

import uds.web.errors as errors
import logging

logger = logging.getLogger(__name__)


def login(request, smallName=None):
    '''
    View responsible of logging in an user
    :param request:  http request
    :param smallName: smallName of login auth
    '''
    # request.session.set_expiry(GlobalConfig.USER_SESSION_LENGTH.getInt())

    host = request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'  # Last one is a placeholder in case we can't locate host name

    # Get Authenticators limitation
    logger.debug('Host: {0}'.format(host))
    if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(True) is True:
        if smallName is None:
            try:
                Authenticator.objects.get(small_name=host)
                smallName = host
            except Exception:
                try:
                    smallName = Authenticator.objects.order_by('priority')[0].small_name
                except Exception:  # There is no authenticators yet, simply allow global login to nowhere.. :-)
                    smallName = None

    logger.debug('Small name: {0}'.format(smallName))

    logger.debug(request.method)
    if request.method == 'POST':
        if 'uds' not in request.COOKIES:
            logger.debug('Request does not have uds cookie')
            return errors.errorView(request, errors.COOKIES_NEEDED)  # We need cookies to keep session data
        request.session.cycle_key()
        form = LoginForm(request.POST, smallName=smallName)
        if form.is_valid():
            java = form.cleaned_data['java'] == 'y'
            os = OsDetector.getOsFromUA(request.META.get('HTTP_USER_AGENT'))
            try:
                authenticator = Authenticator.objects.get(pk=form.cleaned_data['authenticator'])
            except Exception:
                authenticator = Authenticator()
            userName = form.cleaned_data['user']

            cache = Cache('auth')
            cacheKey = str(authenticator.id) + userName
            tries = cache.get(cacheKey)
            if tries is None:
                tries = 0
            if authenticator.getInstance().blockUserOnLoginFailures is True and tries >= GlobalConfig.MAX_LOGIN_TRIES.getInt():
                form.add_form_error('Too many authentication errors. User temporarily  blocked.')
                authLogLogin(request, authenticator, userName, java, os, 'Temporarily blocked')
            else:
                user = authenticate(userName, form.cleaned_data['password'], authenticator)
                logger.debug('User: {}'.format(user))

                if user is None:
                    logger.debug("Invalid credentials for user {0}".format(userName))
                    tries += 1
                    cache.put(cacheKey, tries, GlobalConfig.LOGIN_BLOCK.getInt())
                    form.add_form_error('Invalid credentials')
                    authLogLogin(request, authenticator, userName, java, os, 'Invalid credentials')
                else:
                    logger.debug('User {} has logged in'.format(userName))
                    cache.remove(cacheKey)  # Valid login, remove cached tries
                    response = HttpResponseRedirect(reverse('uds.web.views.index'))
                    webLogin(request, response, user, form.cleaned_data['password'])
                    # Add the "java supported" flag to session
                    request.session['java'] = java
                    request.session['OS'] = os
                    logger.debug('Navigator supports java? {0}'.format(java))
                    authLogLogin(request, authenticator, user.name, java, os)
                    return response
    else:
        form = LoginForm(smallName=smallName)

    response = render_to_response(theme.template('login.html'), {'form': form, 'customHtml': GlobalConfig.CUSTOM_HTML_LOGIN.get(True)},
                                  context_instance=RequestContext(request))

    getUDSCookie(request, response)

    return response


def customAuth(request, idAuth):
    res = ''
    try:
        a = Authenticator.objects.get(pk=idAuth).getInstance()
        res = a.getHtml(request)
        if res is None:
            res = ''
    except Exception:
        logger.exception('customAuth')
        res = 'error'
    return HttpResponse(res, content_type='text/html')


@webLoginRequired
def logout(request):
    authLogLogout(request)
    return webLogout(request, request.user.logout())
