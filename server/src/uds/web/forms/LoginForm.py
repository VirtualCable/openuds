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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.utils.translation import ugettext_lazy as _
from django import forms
from django.forms.forms import NON_FIELD_ERRORS
from django.forms.util import ErrorDict
from uds.models import Authenticator
import logging

logger = logging.getLogger(__name__)

class BaseForm(forms.Form):
    
    def __init__(self, *args, **kwargs):
        super(BaseForm, self).__init__(*args, **kwargs)
    
    def add_form_error(self, message):
        if not self._errors:
            self._errors = ErrorDict()
        if not NON_FIELD_ERRORS in self._errors:
            self._errors[NON_FIELD_ERRORS] = self.error_class()
        self._errors[NON_FIELD_ERRORS].append(message)


class LoginForm(BaseForm):
    user = forms.CharField(label=_('Username'), max_length=64)
    password = forms.CharField(label=_('Password'), widget=forms.PasswordInput({'title': _('Password')}))
    authenticator = forms.ChoiceField(label=_('Authenticator'), choices = ())
    java = forms.CharField(widget = forms.HiddenInput())
    standard = forms.CharField(widget = forms.HiddenInput(), required=False)
    nonStandard = forms.CharField(widget = forms.HiddenInput(), required=False)
    
    def __init__(self, *args, **kwargs):
        # If an specified login is passed in, retrieve it & remove it from kwargs dict
        smallName = kwargs.get('smallName', None) 
        if kwargs.has_key('smallName'):
            del kwargs['smallName']
            
        logger.debug('smallName is "{0}"'.format(smallName))
        
        super(LoginForm, self).__init__(*args, **kwargs)
        choices = []
        nonStandard = []
        standard = []
        
        auths = None
        if smallName is not None:
            auths = Authenticator.objects.filter(small_name=smallName).order_by('priority', 'name')
            if auths.count() == 0:
                auths = Authenticator.objects.all().order_by('priority', 'name')[0:1]
            logger.debug(auths)
            logger.debug(list(auths))
        else:
            auths = Authenticator.objects.all().order_by('priority', 'name')
            
        for a in auths:
            if a.getType() is None:
                continue
            choices.append( (a.id, a.name) )
            if a.getType().isCustom():
                nonStandard.append(str(a.id))
            else:
                standard.append(str(a.id))
            
        self.fields['authenticator'].choices = choices
        self.fields['nonStandard'].initial = ','.join(nonStandard)
        self.fields['standard'].initial = ','.join(standard)
