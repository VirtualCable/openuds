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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

import logging

logger = logging.getLogger(__name__)


def parseDate(dateToParse):
    import datetime
    from django.utils.translation import get_language
    from django.utils import formats
    
    if get_language() == 'fr':
        date_format = '%d/%m/%Y'
    else:
        date_format = formats.get_format('SHORT_DATE_FORMAT').replace('Y', '%Y').replace('m','%m').replace('d','%d')
        
    return datetime.datetime.strptime(dateToParse, date_format).date()
    
def dateToLiteral(date):
    from django.utils.translation import get_language
    from django.utils import formats

    # Fix for FR lang for datepicker
    if get_language() == 'fr':
        date = date.strftime('%d/%m/%Y')
    else:
        date = formats.date_format(date, 'SHORT_DATE_FORMAT') 

    return date

def extractKey(dictionary, key, **kwargs):
    
    format_ = kwargs.get('format', '{0}')
    default = kwargs.get('default', '') 
    
    if dictionary.has_key(key):
        value = format_.format(dictionary[key])
        del dictionary[key]
    else:
        value = default
    return value

def checkBrowser(user_agent, browser):
    '''
    Known browsers right now:
    ie[version]
    ie<[version]
    '''
    import re
    # Split brwosers we look for
    needs_msie = False
    needs_version = 6
    needs = '='
    
    if browser[:2] == 'ie':
        needs_msie = True
        if browser[2] == '<' or browser[2] == '>' or browser[2] == '=':
            needs = browser[2]
            needs_version = int(browser[3:])
        else:
            needs_version = int(browser[2:])
    
    try:
        if needs_msie:
            msie = re.compile('MSIE ([0-9]+)\.([0-9]+)')
            matches = msie.search(user_agent)
            if matches is None:
                return False
            version = int(matches.groups()[0])
            if needs == '<':
                return version < needs_version
            elif needs == '>':
                return version > needs_version
            
            return version == needs_version
    except:
        return False
        
