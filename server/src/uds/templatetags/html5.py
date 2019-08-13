# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2016 Virtual Cable S.L.
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
from django.utils.translation import ugettext as _
from django.templatetags.static import static
from django.utils.html import mark_safe

from uds.core.util import html
from uds.core.auths.auth import ROOT_ID
from uds.core.util.Config import GlobalConfig
from uds.models.image import Image
from uds.core.managers.UserPrefsManager import UserPrefsManager
from uds.REST.methods.client import CLIENT_VERSION

import logging

logger = logging.getLogger(__name__)

register = template.Library()


@register.simple_tag
def calendar_denied_msg():
    text = GlobalConfig.LIMITED_BY_CALENDAR_TEXT.get().strip()
    if text == '':
        text = _("Access limited by calendar")

    return text


# Browser related
class IfBrowser(template.Node):

    def __init__(self, nodelistTrue, nodelistFalse, browsers):
        self._nodelistTrue = nodelistTrue
        self._nodelistFalse = nodelistFalse
        self._browsers = browsers

    def render(self, context):
        if 'request' in context:
            for b in self._browsers:
                if html.checkBrowser(context['request'], b):
                    return self._nodelistTrue.render(context)
            if self._nodelistFalse is None:
                return ''
        else:
            return ''

        return self._nodelistFalse.render(context)


@register.tag(name='ifbrowser')
def ifbrowser(parser, token):
    cmd = token.split_contents()
    try:
        browsers = cmd[1:]
    except Exception:
        raise template.TemplateSyntaxError('{0} tag requires browsers to be checked')

    states = {}

    default_states = ['ifbrowser', 'else']
    end_tag = 'endifbrowser'

    while token.contents != end_tag:
        current = token.contents
        states[current.split()[0]] = parser.parse(default_states + [end_tag])
        token = parser.next_token()

    return IfBrowser(states['ifbrowser'], states.get('else', None), browsers)


# Os Related
@register.filter(name='osName')
def osName(os):
    if os == 'windows':
        return 'Windows'
    elif os == 'linux':
        return 'Linux'
    else:
        return 'Mac OS X'


@register.filter(name='pluginDownloadUrl')
def pluginDownloadUrl(os):
    tmpl = '<a href="{url}" class="btn btn-success">' + _('Download UDS Plugin for') + ' {os}</a>'

    if os == 'windows':
        return tmpl.format(url=static('clients/UDSClientSetup-{version}.exe'.format(version=CLIENT_VERSION)), os='Windows')
    elif os == 'linux':
        linux_packages = (
            ('udsclient_{version}_all.deb'.format(version=CLIENT_VERSION), _('Debian based Linux') + ' ' + _('(requires Python-2.7)')),
            ('udsclient-{version}-1.noarch.rpm'.format(version=CLIENT_VERSION), _('Red Hat based Linux (RH, Fedora, Centos, ...)') + ' ' + _('(requires Python-2.7)')),
            ('udsclient-opensuse-{version}-1.noarch.rpm'.format(version=CLIENT_VERSION), _('Suse based Linux') + ' ' + _('(requires Python-2.7)')),
            ('udsclient-{version}.tar.gz'.format(version=CLIENT_VERSION), _('Generic .tar.gz Linux') + ' ' + _('(requires Python-2.7)'))
        )
        res = ''
        for v in linux_packages:
            res += '<p class="text-center">' + tmpl.format(url=static('clients/' + v[0]), os=v[1]) + '</p>'
        return res
    else:
        return tmpl.format(url=static('clients/UDSClient-{version}.pkg'.format(version=CLIENT_VERSION)), os='Mac OSX')
