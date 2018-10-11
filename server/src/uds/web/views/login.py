# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2018 Virtual Cable S.L.
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

from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from uds.core.auths.auth import webLogin, authLogLogout, getUDSCookie, webLoginRequired, webLogout
from uds.models import Authenticator
from uds.web.forms.LoginForm import LoginForm
from uds.core.util.Config import GlobalConfig
from uds.core.util.model import processUuid

from uds.web.authentication import checkLogin

from uds.core.ui import theme
from uds.core import VERSION

import uds.web.util.errors as errors
import logging

logger = logging.getLogger(__name__)
__updated__ = '2018-09-12'


# Allow cross-domain login
# @csrf_exempt
def login(request, tag=None):
    """
    View responsible of logging in an user
    :param request:  http request
    :param tag: tag of login auth
    """
    # request.session.set_expiry(GlobalConfig.USER_SESSION_LENGTH.getInt())
    response = None

    # Default empty form
    form = LoginForm(tag=tag)

    if request.method == 'POST':
        form = LoginForm(request.POST, tag=tag)
        user, data = checkLogin(request, form, tag)
        if user:
            response = HttpResponseRedirect(reverse('uds.web.views.index'))
            webLogin(request, response, user, data)  # data is user password here
        else:  # error, data = error
            if isinstance(data, int):
                return errors.errorView(request, data)
            # Error to notify
            form.add_error(None, data)

    if response is None:
        response = render(request,
            theme.template('login.html'),
            {
                'form': form,
                'authenticators': Authenticator.getByTag(tag),
                'customHtml': GlobalConfig.CUSTOM_HTML_LOGIN.get(True),
                'version': VERSION

            }
        )

    getUDSCookie(request, response)

    return response


@webLoginRequired(admin=False)
def logout(request):
    authLogLogout(request)
    logoutUrl = request.user.logout()
    if logoutUrl is None:
        logoutUrl = request.session.get('logouturl', None)
    return webLogout(request, logoutUrl)
