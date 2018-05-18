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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import json

import logging

from django import template
from django.conf import settings
from django.utils.translation import gettext, get_language
from django.utils.html import mark_safe
from django.urls import reverse
from django.templatetags.static import static

from uds.REST.methods.client import CLIENT_VERSION
from uds.core.managers import downloadsManager

logger = logging.getLogger(__name__)

register = template.Library()

CSRF_FIELD = 'csrfmiddlewaretoken'


@register.simple_tag(takes_context=True)
def udsJs(context):
    request = context['request']

    profile = {
        'user': None if request.user is None else request.user.name,
        'role': 'staff' if request.user and request.user.staff_member else 'user',
    }

    # Gets csrf token
    csrf_token = context.get('csrf_token')
    if csrf_token is not None:
        csrf_token = str(csrf_token)

    config = {
        'language': get_language(),
        'available_languages': [{'id': k, 'name': gettext(v)} for k, v in settings.LANGUAGES],
        'os': request.os['OS'],
        'csrf_field': CSRF_FIELD,
        'csrf': csrf_token,
        'urls': {
            'lang': reverse('set_language'),
            'logout': reverse('uds.web.views.logout')
        }
    }

    plugins = [
        {
            'url': static(url.format(version=CLIENT_VERSION)),
            'description': description,
            'name': name
        } for url, description, name in (
            ('clients/UDSClientSetup-{version}.exe', gettext('Windows plugin'), 'Windows'),
            ('clients/UDSClient-{version}.pkg', gettext('Mac OS X plugin'), 'MacOS'),
            ('udsclient_{version}_all.deb', gettext('Debian based Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-{version}-1.noarch.rpm', gettext('Red Hat based Linux (RH, Fedora, Centos, ...)') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-opensuse-{version}-1.noarch.rpm', gettext('Suse based Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-{version}.tar.gz', gettext('Generic .tar.gz Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux')
        )
    ]

    actors = [];

    if profile['role'] == 'staff':  # Add staff things
        actors = [{'url': reverse('uds.web.views.download', kwargs={'idDownload': key}), 'name': val['name'], 'description': gettext(val['comment'])} for key, val in downloadsManager().getDownloadables().items()]
        config['urls']['admin'] = reverse('uds.admin.views.index')

    uds = {
        'profile': profile,
        'config': config,
        'plugins': plugins,
        'actors': actors
    }

    javascript = 'var udsData = ' + json.dumps(uds) + ';\n';

    return mark_safe(javascript);
