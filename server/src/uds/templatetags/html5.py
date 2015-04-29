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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django import template
from django.utils.translation import ugettext as _
from django.templatetags.static import static

from uds.core.util import html
from uds.core.util.request import getRequest
from uds.core.auths.auth import ROOT_ID
from uds.core.util.Config import GlobalConfig
from uds.models.Image import Image
from uds.core.managers.UserPrefsManager import UserPrefsManager

import logging

logger = logging.getLogger(__name__)

register = template.Library()


# locale related
@register.filter(name='country')
def country(lang):
    if lang == 'en':
        return 'US'
    if lang == 'ja':
        return 'JP'

    return lang.upper()


# Config related
@register.assignment_tag
def get_theme():
    return GlobalConfig.UDS_THEME.get()


class EnhacedVisual(template.Node):
    def __init__(self, nodelistTrue, nodelistFalse):
        self._nodelistTrue = nodelistTrue
        self._nodelistFalse = nodelistFalse

    def render(self, context):
        if GlobalConfig.UDS_THEME_VISUAL.getBool(True) is True:
            return self._nodelistTrue.render(context)
        if self._nodelistFalse is None:
            return ''

        return self._nodelistFalse.render(context)


@register.tag(name='enhaced_visual')
def enhaced_visual(parser, token):
    states = {}

    default_states = ['enhaced_visual', 'else']
    end_tag = 'endenhaced_visual'

    while token.contents != end_tag:
        current = token.contents
        states[current.split()[0]] = parser.parse(default_states + [end_tag])
        token = parser.next_token()

    return EnhacedVisual(states['enhaced_visual'], states.get('else', None))


class TabIndex(template.Node):
    def __init__(self, tabIndexName):
        self.tabIndexIname = tabIndexName

    def render(self, context):
        counter = context.get(self.tabIndexIname, 0) + 1
        context[self.tabIndexIname] = counter
        return "{}".format(counter)


@register.tag(name='tabindex')
def tabindex(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, tabIndexName = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0]
        )

    return TabIndex(tabIndexName)


class Preference(template.Node):
    def __init__(self, modName, prefName):
        self.modName = modName
        self.prefName = prefName

    def render(self, context):
        if context.get('user') is None:
            return ''

        prefs = context['user'].prefs(self.modName)
        return prefs.get(self.prefName)


@register.tag(name='preference')
def preference(parser, token):
    try:
        # split_contents() knows not to split quoted strings.
        tag_name, rest = token.split_contents()
        modName, prefName = rest.split('.')
    except ValueError:
        raise template.TemplateSyntaxError(
            "%r tag requires a single argument" % token.contents.split()[0]
        )

    return Preference(modName, prefName)


@register.assignment_tag
def preferences_allowed():
    return GlobalConfig.PREFERENCES_ALLOWED.getBool(True)


@register.assignment_tag
def root_id():
    return ROOT_ID


@register.assignment_tag
def image_size():
    return Image.MAX_IMAGE_SIZE


# Browser related
class IfBrowser(template.Node):
    def __init__(self, nodelistTrue, nodelistFalse, browsers):
        self._nodelistTrue = nodelistTrue
        self._nodelistFalse = nodelistFalse
        self._browsers = browsers

    def render(self, context):
        if 'request' in context:
            user_agent = context['request'].META.get('HTTP_USER_AGENT', 'Unknown')
        else:
            user_agent = 'Unknown'
        for b in self._browsers:
            if html.checkBrowser(user_agent, b):
                return self._nodelistTrue.render(context)
        if self._nodelistFalse is None:
            return ''

        return self._nodelistFalse.render(context)


@register.tag(name='ifbrowser')
def ifbrowser(parser, token):
    cmd = token.split_contents()
    try:
        browsers = cmd[1:]
    except:
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
        return 'Windows platform'
    elif os == 'linux':
        return 'Linux platform'
    else:
        return 'Mac OSX platform'


@register.filter(name='pluginDownloadUrl')
def pluginDownloadUrl(os):
    tmpl = '<a href="{url}" class="btn btn-success">' + _('Download UDS Plugin for') + ' {os}</a>'

    if os == 'windows':
        return tmpl.format(url=static('clients/UDSClientSetup.exe'), os='Windows')
    elif os == 'linux':
        linux_packages = (
            ('udsclient_1.7.5_all.deb', _('Debian based Linux')),
            ('udsclient-1.7.5-1.noarch.rpm', _('Red Hat based Linux (RH, Fedora, Centos, ...)')),
            ('udsclient-opensuse-1.7.5-1.noarch.rpm', _('Suse based Linux')),
            ('udsclient-1.7.5.tar.gz', _('Generic .tar.gz Linux'))
        )
        res = ''
        for v in linux_packages:
            res += '<p class="text-center">' + tmpl.format(url=static('clients/' + v[0]), os=v[1]) + '</p>'
        return res
    else:
        return tmpl.format(url=static('clients/UDSClient.pkg'), os='Mac OSX')
