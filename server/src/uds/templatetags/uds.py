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
from django.templatetags.static import static
from uds.REST.methods.client import CLIENT_VERSION

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def javascript_auths(authenticators):
    res = []
    for a in authenticators:
        theType = a.getType()
        res.append({
            'authId': a.uuid,
            'authSmallName': str(a.small_name),
            'auth': a.name,
            'type': theType.typeType,
            'priority': a.priority,
            'isCustom': theType.isCustom()
        })
    return mark_safe('<script type="text/javascript">\nvar authenticators = ' + json.dumps(res, indent=4) + ';\n</script>')


@register.simple_tag
def udsJs(request):
    udsConfig = {
        'language': get_language(),
        'available_languages': [{'id': k, 'name': gettext(v)} for k, v in settings.LANGUAGES],
        'os': request.os['OS'],
    }

    packages = (
        ('clients/UDSClientSetup-{version}.exe'.format(version=CLIENT_VERSION), gettext('Debian based Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
        ('udsclient_{version}_all.deb'.format(version=CLIENT_VERSION), gettext('Debian based Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
        ('udsclient-{version}-1.noarch.rpm'.format(version=CLIENT_VERSION), gettext('Red Hat based Linux (RH, Fedora, Centos, ...)') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
        ('udsclient-opensuse-{version}-1.noarch.rpm'.format(version=CLIENT_VERSION), gettext('Suse based Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
        ('udsclient-{version}.tar.gz'.format(version=CLIENT_VERSION), gettext('Generic .tar.gz Linux') + ' ' + gettext('(requires Python-2.7)'), 'Linux')
    )

    udsPlugins = [
        {
            'url': static(url),
            'description': description,
            'os': os
        } for url, description, os in packages
    ]

    javascript = 'var udsConfig = ' + json.dumps(udsConfig) + ';\n';
    javascript += 'var plugins = ';
    return mark_safe(javascript);
