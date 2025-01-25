# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import typing
import logging

from django.http import HttpResponse
from django.middleware import csrf
from django.shortcuts import render
from django.utils.translation import gettext as _

from uds.core import consts
from uds.core.auths.auth import weblogin_required

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


@weblogin_required(role=consts.Roles.ADMIN)
def index(request: 'HttpRequest') -> HttpResponse:
    # Gets csrf token
    csrf_token = csrf.get_token(request)

    return render(
        request,
        'uds/admin/index.html',
        {'csrf_field': consts.auth.CSRF_FIELD, 'csrf_token': csrf_token},
    )

# from django.template import RequestContext, loader
# @weblogin_required(role=consts.Roles.ADMIN)
# def tmpl(request: 'HttpRequest', template: str) -> HttpResponse:
#     try:
#         t = loader.get_template('uds/admin/tmpl/' + template + ".html")
#         c = RequestContext(request)
#         resp = t.render(c.flatten())
#     except Exception as e:
#         logger.debug('Exception getting template: %s', e)
#         resp = _('requested a template that do not exist')
#     return HttpResponse(resp, content_type="text/plain")
