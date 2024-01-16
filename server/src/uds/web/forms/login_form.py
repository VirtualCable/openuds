# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy as _
from django import forms
from uds.models import Authenticator


logger = logging.getLogger(__name__)


class LoginForm(forms.Form):
    user = forms.CharField(label=_('Username'), max_length=64, widget=forms.TextInput())
    password = forms.CharField(
        label=_('Password'),
        widget=forms.PasswordInput(attrs={'title': _('Password')}),
        required=False,
    )
    authenticator = forms.ChoiceField(
        label=_('Authenticator'), choices=(), required=False
    )
    logouturl = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        # If an specified login is passed in, retrieve it & remove it from kwargs dict
        tag = kwargs.get('tag', None)
        if 'tag' in kwargs:
            del kwargs['tag']

        # Parent init
        super(LoginForm, self).__init__(*args, **kwargs)

        choices = []

        for a in Authenticator.get_by_tag(tag):
            if not a.get_type():  # Not existing manager for the auth?
                continue
            if a.get_type().is_custom() and tag == 'disabled':
                continue
            choices.append((a.uuid, a.name))

        typing.cast(forms.ChoiceField, self.fields['authenticator']).choices = choices  
