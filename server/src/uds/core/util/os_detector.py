# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import enum
import re
import logging
import typing

logger = logging.getLogger(__name__)


class DetectedOsInfo(typing.NamedTuple):
    os: 'KnownOS'
    browser: 'KnownBrowser'
    version: str


class KnownOS(enum.Enum):
    Linux = ('Linux', 'armv7l')
    ChromeOS = ('CrOS',)
    WindowsPhone = ('Windows Phone',)
    Windows = ('Windows',)
    MacOS = ('MacOsX',)
    Android = ('Android',)
    iPad = ('iPad',)  #
    iPhone = ('iPhone',)  # In fact, these are IOS both, but we can diferentiate them
    WYSE = ('WYSE',)
    Unknown = ('Unknown',)

    def os_name(self):
        return self.value[0].lower()

knownOss = tuple(os for os in KnownOS if os != KnownOS.Unknown)

allOss = knownOss + (KnownOS.Unknown,)
desktopOss = (KnownOS.Linux, KnownOS.Windows, KnownOS.MacOS)
mobilesODD = list(set(allOss) - set(desktopOss))


DEFAULT_OS = KnownOS.Windows

class KnownBrowser(enum.Enum):
    # Known browsers
    Firefox = 'Firefox'
    Seamonkey = 'Seamonkey'
    Chrome = 'Chrome'
    Chromium = 'Chromium'
    Safari = 'Safari'
    Opera = 'Opera'
    IExplorer = 'Explorer'
    Other = 'Other'

knownBrowsers = tuple(KnownBrowser)

browsersREs: typing.Dict[KnownBrowser, typing.Tuple] = {
    KnownBrowser.Firefox: (re.compile(r'Firefox/([0-9.]+)'),),
    KnownBrowser.Seamonkey: (re.compile(r'Seamonkey/([0-9.]+)'),),
    KnownBrowser.Chrome: (re.compile(r'Chrome/([0-9.]+)'),),
    KnownBrowser.Chromium: (re.compile(r'Chromium/([0-9.]+)'),),
    KnownBrowser.Safari: (re.compile(r'Safari/([0-9.]+)'),),
    KnownBrowser.Opera: (
        re.compile(r'OPR/([0-9.]+)'),
        re.compile(r'Opera/([0-9.]+)'),
    ),
    KnownBrowser.IExplorer: (
        re.compile(r';MSIE ([0-9.]+);'),
        re.compile(r'Trident/.*rv:([0-9.]+)'),
    ),
}

browserRules: typing.Dict[KnownBrowser, typing.Tuple] = {
    KnownBrowser.Chrome: (KnownBrowser.Chrome, (KnownBrowser.Chromium, KnownBrowser.Opera)),
    KnownBrowser.Firefox: (KnownBrowser.Firefox, (KnownBrowser.Seamonkey,)),
    KnownBrowser.IExplorer: (KnownBrowser.IExplorer, ()),
    KnownBrowser.Chromium: (KnownBrowser.Chromium, (KnownBrowser.Chrome,)),
    KnownBrowser.Safari: (KnownBrowser.Safari, (KnownBrowser.Chrome, KnownBrowser.Chromium, KnownBrowser.Opera)),
    KnownBrowser.Seamonkey: (KnownBrowser.Seamonkey, (KnownBrowser.Firefox,)),
    KnownBrowser.Opera: (KnownBrowser.Opera, ()),
}


def getOsFromUA(
    ua: typing.Optional[str],
) -> DetectedOsInfo:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = ua or KnownOS.Unknown.value[0]

    res = DetectedOsInfo(os=KnownOS.Unknown, browser=KnownBrowser.Other, version='0.0')
    found: bool = False
    for os in knownOss:
        if found:
            break
        for osName in os.value:
            if osName in ua:
                res = res._replace(os=os)
                found = True
                break

    match = None

    ruleKey, ruleValue = None, None
    for ruleKey, ruleValue in browserRules.items():
        must, mustNot = ruleValue

        for mustRe in browsersREs[must]:
            match = mustRe.search(ua)
            if match is None:
                continue
            # Check against no maching rules
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
        res = res._replace(browser=ruleKey, version=match.groups(1)[0])

    return res
