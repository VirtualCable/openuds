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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import get_language
from uds.core.util import OsDetector
from django.utils import formats

import six
import logging

__updated__ = '2015-05-03'

logger = logging.getLogger(__name__)


def udsLink(request, ticket, scrambler):

    if request.is_secure():
        proto = 'udss'
    else:
        proto = 'uds'

    return "{}://{}{}/{}".format(proto, request.build_absolute_uri('/').split('//')[1], ticket, scrambler)


def udsAccessLink(request, serviceId, transportId):
    return 'udsa://{}/{}'.format(serviceId, transportId)


def parseDate(dateToParse):
    import datetime

    if get_language() == 'fr':
        date_format = '%d/%m/%Y'
    else:
        date_format = formats.get_format('SHORT_DATE_FORMAT').replace('Y', '%Y').replace('m', '%m').replace('d', '%d')  # pylint: disable=maybe-no-member

    return datetime.datetime.strptime(dateToParse, date_format).date()


def dateToLiteral(date):
    # Fix for FR lang for datepicker
    if get_language() == 'fr':
        date = date.strftime('%d/%m/%Y')
    else:
        date = formats.date_format(date, 'SHORT_DATE_FORMAT')

    return date


def extractKey(dictionary, key, **kwargs):

    format_ = kwargs.get('format', '{0}')
    default = kwargs.get('default', '')

    if key in dictionary:
        value = format_.format(dictionary[key])
        del dictionary[key]
    else:
        value = default
    return value


_browsers = {
    'ie': [OsDetector.IExplorer],
    'opera': [OsDetector.Opera],
    'firefox': [OsDetector.Firefox, OsDetector.Seamonkey],
    'chrome': [OsDetector.Chrome, OsDetector.Chromium],
    'safari': [OsDetector.Safari],
}


def checkBrowser(request, browser):
    """
    Known browsers right now:
    ie[version]
    ie<[version]
    """
    # Split brwosers we look for
    needs_version = 0
    needs = ''

    for b, requires in six.iteritems(_browsers):
        if browser.startswith(b):
            if request.os.Browser not in requires:
                return False
            browser = browser[len(b):]
            break

    browser += ' '  # So we ensure we have at least beowser 0

    if browser[0] == '<' or browser[0] == '>' or browser[0] == '=':
        needs = browser[0]
        needs_version = int(browser[1:])
    else:
        try:
            needs = '='
            needs_version = int(browser)
        except Exception:
            needs = ''
            needs_version = 0

    try:
        version = int(request.os.Version.split('.')[0])
        if needs == '<':
            return version < needs_version
        elif needs == '>':
            return version > needs_version
        elif needs == '=':
            return version == needs_version

        return True
    except Exception:
        return False


# debug setting in context
def context(request):
    from django.conf import settings
    return {'DEBUG': settings.DEBUG}
