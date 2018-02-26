# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _, ugettext
from django import forms
from django.utils.safestring import mark_safe
from uds.models import Authenticator

import six
import logging

logger = logging.getLogger(__name__)

# pylint: disable=no-value-for-parameter, unexpected-keyword-arg


class CustomSelect(forms.Select):

    bootstrap = False

    def render(self, name, value, attrs=None, **kwargs):
        if len(self.choices) < 2:
            visible = ' style="display: none;"'
        else:
            visible = ''
        res = '<select id="id_{0}" name="{0}" class="selectpicker show-menu-arrow" data-header="{1}" data-size="8" data-width="100%" >'.format(name, ugettext('Select authenticator'))
        for choice in self.choices:
            res += '<option value="{0}">{1}</option>'.format(choice[0], choice[1])
        res += '</select>'
        return mark_safe('<div class="form-group"{0}><label>'.format(visible) + six.text_type(_('authenticator')) + '</label>' + res + '</div>')


class LoginForm(forms.Form):
    user = forms.CharField(label=_('Username'), max_length=64, widget=forms.TextInput())
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput(attrs={'title': _('Password')}), required=False)
    authenticator = forms.ChoiceField(label=_('Authenticator'), choices=(), widget=CustomSelect(), required=False)
    standard = forms.CharField(widget=forms.HiddenInput(), required=False)
    nonStandard = forms.CharField(widget=forms.HiddenInput(), required=False)
    logouturl = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        # If an specified login is passed in, retrieve it & remove it from kwargs dict
        tag = kwargs.get('tag', None)
        if 'tag' in kwargs:
            del kwargs['tag']

        logger.debug('tag is "{0}"'.format(tag))

        super(LoginForm, self).__init__(*args, **kwargs)
        choices = []
        nonStandard = []
        standard = []

        auths = None
        if tag is not None:
            auths = Authenticator.objects.filter(small_name=tag).order_by('priority', 'name')
            if auths.count() == 0:
                auths = Authenticator.objects.all().order_by('priority', 'name')[0:1]
            logger.debug(auths)
            logger.debug(list(auths))
        else:
            auths = Authenticator.objects.all().order_by('priority', 'name')

        for a in auths:
            if a.getType() is None:
                continue
            if a.getType().isCustom() and tag == 'disabled':
                continue
            choices.append((a.uuid, a.name))
            if a.getType().isCustom():
                nonStandard.append(a.uuid)
            else:
                standard.append(a.uuid)

        self.fields['authenticator'].choices = choices
        self.fields['nonStandard'].initial = ','.join(nonStandard)
        self.fields['standard'].initial = ','.join(standard)
