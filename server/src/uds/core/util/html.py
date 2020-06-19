# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import datetime
import logging
import typing

from django.utils.translation import get_language
from django.utils import formats
from uds.core.util import os_detector as OsDetector

if typing.TYPE_CHECKING:
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

logger = logging.getLogger(__name__)

_browsers: typing.Dict[str, typing.Tuple] = {
    'ie': (OsDetector.IExplorer,),
    'opera': (OsDetector.Opera,),
    'firefox': (OsDetector.Firefox, OsDetector.Seamonkey),
    'chrome': (OsDetector.Chrome, OsDetector.Chromium),
    'safari': (OsDetector.Safari,),
}


def udsLink(request: 'HttpRequest', ticket: str, scrambler: str) -> str:

    if request.is_secure():
        proto = 'udss'
    else:
        proto = 'uds'

    return "{}://{}{}/{}".format(proto, request.build_absolute_uri('/').split('//')[1], ticket, scrambler)


def udsAccessLink(request: 'HttpRequest', serviceId: str, transportId: str) -> str:
    return 'udsa://{}/{}'.format(serviceId, transportId)


def udsMetaLink(request: 'HttpRequest', serviceId: str) -> str:
    return 'udsa://{}/{}'.format(serviceId, 'meta')


def parseDate(dateToParse) -> datetime.date:
    if get_language() == 'fr':
        date_format = '%d/%m/%Y'
    else:
        date_format = formats.get_format('SHORT_DATE_FORMAT').replace('Y', '%Y').replace('m', '%m').replace('d', '%d')  # pylint: disable=maybe-no-member

    return datetime.datetime.strptime(dateToParse, date_format).date()


def dateToLiteral(date) -> str:
    # Fix for FR lang for datepicker
    if get_language() == 'fr':
        date = date.strftime('%d/%m/%Y')
    else:
        date = formats.date_format(date, 'SHORT_DATE_FORMAT')

    return date


def extractKey(dictionary: typing.Dict, key: typing.Any, **kwargs) -> str:
    format_ = kwargs.get('format', '{0}')
    default = kwargs.get('default', '')

    if key in dictionary:
        value = format_.format(dictionary[key])
        del dictionary[key]
    else:
        value = default
    return value


def checkBrowser(request: 'HttpRequest', browser: str) -> bool:
    """
    Known browsers right now:
    ie[version]
    ie<[version]
    """
    # Split brwosers we look for
    needs_version = 0
    needs = ''

    for b, requires in _browsers.items():
        if browser.startswith(b):
            if request.os.Browser not in requires:
                return False
            browser = browser[len(b):]  # remove "browser name" from string
            break

    browser += ' '  # So we ensure we have at least beowser[0]

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
        if needs == '>':
            return version > needs_version
        if needs == '=':
            return version == needs_version

        return True
    except Exception:
        return False
