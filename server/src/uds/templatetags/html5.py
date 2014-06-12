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
from uds.core.util import html
from uds.core.util.Config import GlobalConfig

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
        if GlobalConfig.UDS_THEME_VISUAL.getBool() is True:
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
