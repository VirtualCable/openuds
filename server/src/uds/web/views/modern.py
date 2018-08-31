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
import logging
import json

from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from uds.core.auths.auth import (
    getUDSCookie,
    denyNonAuthenticated
)
from uds.web.services import getServicesData

logger = logging.getLogger(__name__)


def index(request):
    response = render(request, 'uds/modern/index.html', {})

    logger.debug('Session expires at %s', request.session.get_expiry_date())

    # Ensure UDS cookie is present
    getUDSCookie(request, response)

    return response


# Basically, the original /login method, but fixed for modern interface
def login(request, tag=None):
    from uds.web.forms.LoginForm import LoginForm
    from uds.web.authentication import checkLogin
    from uds.core.auths.auth import webLogin
    from django.http import HttpResponseRedirect

    # Default empty form
    if request.method == 'POST':
        form = LoginForm(request.POST, tag=tag)
        user, data = checkLogin(request, form, tag)
        if user:
            response = HttpResponseRedirect(reverse('modern.index'))
            webLogin(request, response, user, data)  # data is user password here
        else:
            # If error is numeric, redirect...
            # Error, set error on session for process for js
            request.session['errors'] = data
            return HttpResponse(data);
    else:
        response = index(request)

    return response


def js(request):
    return render(request, 'uds/js.js', content_type='text/javascript')


@denyNonAuthenticated
def services(request):
    data = getServicesData(request)

    return HttpResponse(content=json.dumps(data), content_type='application/json')

