# -*- coding: utf-8 -*-
#
# Copyright (c) 2018-2023 Virtual Cable S.L.U.
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

from django.http import HttpRequest, HttpResponse
from django.middleware import csrf
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from uds.core import consts, types
from uds.core.auths import auth
from uds.web.util import configjs

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    pass


@never_cache
def index(request: HttpRequest) -> HttpResponse:
    # Gets csrf token
    csrf_token = csrf.get_token(request)

    response = render(
        request=request,
        template_name='uds/modern/index.html',
        context={'csrf_field': consts.auth.CSRF_FIELD, 'csrf_token': csrf_token},
    )

    # Ensure UDS cookie is present
    auth.uds_cookie(request, response)

    return response


# Launches the service using a ticket (for example, from external portal)
@never_cache
def ticket_launcher(request: HttpRequest) -> HttpResponse:
    return index(request)


# Javascript configuration
@never_cache
def js(request: types.requests.ExtendedHttpRequest) -> HttpResponse:
    return HttpResponse(content=configjs.uds_js(request), content_type='application/javascript')
