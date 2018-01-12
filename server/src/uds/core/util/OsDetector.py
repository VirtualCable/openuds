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
from __future__ import unicode_literals

import re
import logging
from .tools import DictAsObj

logger = logging.getLogger(__name__)

# Knowns OSs
Linux = 'Linux'
WindowsPhone = 'Windows Phone'
Windows = 'Windows'
Macintosh = 'Mac'
Android = 'Android'
iPad = 'iPad'
iPhone = 'iPhone'
Unknown = 'Unknown'

knownOss = (WindowsPhone, Android, Linux, Windows, Macintosh, iPad, iPhone)  # Android is linux also, so it is cheched on first place

allOss = tuple(knownOss) + tuple(Unknown)
desktopOss = (Linux, Windows, Macintosh)
mobilesODD = list(set(allOss) - set(desktopOss))

DEFAULT_OS = 'Windows'

# Known browsers
Firefox = 'Firefox'
Seamonkey = 'Seamonkey'
Chrome = 'Chrome'
Chromium = 'Chromium'
Safari = 'Safari'
Opera = 'Opera'
IExplorer = 'Explorer'
Other = 'Other'

knownBrowsers = (Firefox, Seamonkey, Chrome, Chromium, Safari, Opera, IExplorer, Other)

browsersREs = {
    Firefox: (re.compile(r'Firefox/([0-9.]+)'),),
    Seamonkey: (re.compile(r'Seamonkey/([0-9.]+)'),),
    Chrome: (re.compile(r'Chrome/([0-9.]+)'),),
    Chromium: (re.compile(r'Chromium/([0-9.]+)'),),
    Safari: (re.compile(r'Safari/([0-9.]+)'),),
    Opera: (re.compile(r'OPR/([0-9.]+)'), re.compile(r'Opera/([0-9.]+)'),),
    IExplorer: (re.compile(r';MSIE ([0-9.]+);'), re.compile(r'Trident/.*rv:([0-9.]+)'),)
}

browserRules = {
    Chrome: (Chrome, (Chromium, Opera)),
    Firefox: (Firefox, (Seamonkey,)),
    IExplorer: (IExplorer, ()),
    Chromium: (Chromium, (Chrome,)),
    Safari: (Safari, (Chrome, Chromium, Opera)),
    Seamonkey: (Seamonkey, (Firefox,)),
    Opera: (Opera, ()),
}


def getOsFromUA(ua):
    '''
    Basic OS Client detector (very basic indeed :-))
    '''
    if ua is None:
        ua = Unknown

    os = Android

    res = DictAsObj({'OS': os, 'Version': '0.0', 'Browser': 'unknown'})
    for os in knownOss:
        try:
            ua.index(os)
            res.OS = os
            break
        except Exception:
            pass

    match = None

    for ruleKey, ruleValue in browserRules.iteritems():
        must, mustNot = ruleValue

        for mustRe in browsersREs[must]:
            match = mustRe.search(ua)
            if match is None:
                continue
            # Check against no machin rules
            for mustNotREs in mustNot:
                for cre in browsersREs[mustNotREs]:
                    if cre.search(ua) is not None:
                        match = None
                        break
                if match is None:
                    break
            if match is not None:
                break
        if match is not None:
            break

    if match is not None:
        res.Browser = ruleKey  # pylint: disable=undefined-loop-variable
        res.Version = match.groups(1)[0]

    return res


def getOsFromRequest(request):
    try:
        return request.os
    except Exception:
        request.os = getOsFromUA(request.META.get('HTTP_USER_AGENT'))

    return request.os
