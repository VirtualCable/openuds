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

from django.http import HttpResponse
from django.shortcuts import render
from django.template import RequestContext, loader
from django.utils.translation import ugettext as _

from uds.core.auths.auth import webLoginRequired
from uds.core.util.decorators import denyBrowsers

logger = logging.getLogger(__name__)


@denyBrowsers(browsers=['ie<10'])
@webLoginRequired(admin=True)
def index(request):
    return render(request, 'uds/admin/index.html')


@denyBrowsers(browsers=['ie<10'])
@webLoginRequired(admin=True)
def tmpl(request, template):
    try:
        t = loader.get_template('uds/admin/tmpl/' + template + ".html")
        c = RequestContext(request)
        resp = t.render(c.flatten())
    except Exception as e:
        logger.debug('Exception getting template: {0}'.format(e))
        resp = _('requested a template that do not exist')
    return HttpResponse(resp, content_type="text/plain")


@denyBrowsers(browsers=['ie<10'])
@webLoginRequired(admin=True)
def sample(request):
    return render(request, 'uds/admin/sample.html')
