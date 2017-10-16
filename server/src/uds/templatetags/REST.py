# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django import template
from django.conf import settings
from django.utils import safestring
from uds.REST import AUTH_TOKEN_HEADER
import re

import logging

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag(name='auth_token', takes_context=True)
def auth_token(context):
    """
    Returns the authentication token
    """
    request = context['request']
    return request.session.session_key


@register.simple_tag(name='auth_token_header')
def auth_token_header():
    return AUTH_TOKEN_HEADER


@register.simple_tag(name='js_template_path', takes_context=True)
def js_template_path(context, path):
    context['template_path'] = path
    return ''


@register.simple_tag(name='js_template', takes_context=True)
def js_template(context, template_name, template_id=None):
    template_id = (template_id or 'tmpl_' + template_name).replace('/', '_')
    tmpl = template.loader.get_template(context['template_path'] + '/' + template_name + '.html').render(
        context.flatten())
    # Clean tmpl
    if not settings.DEBUG:
        tmpl = re.sub(r'\s+', ' ', tmpl)
    return safestring.mark_safe('<script id="{0}" type="template/uds">{1}</script>'.format(template_id, tmpl))


@register.simple_tag(name='js_template_jade', takes_context=True)
def js_template_jade(context, template_name, template_id=None):
    template_id = (template_id or 'tmpl_' + template_name).replace('/', '_')
    tmpl = template.loader.get_template(context['template_path'] + '/' + template_name + '.jade').render(
        context.flatten())
    # Clean tmpl
    if not settings.DEBUG:
        tmpl = re.sub('\s+', ' ', tmpl)
    return safestring.mark_safe('<script id="{0}" type="template/uds">{1}</script>'.format(template_id, tmpl))
