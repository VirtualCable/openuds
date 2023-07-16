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
    LINUX = ('Linux', 'armv7l')
    CHROME_OS = ('CrOS',)
    WINDOWS_PHONE = ('Windows Phone',)
    WINDOWS = ('Windows',)
    MAC_OS = ('MacOsX',)
    ANDROID = ('Android',)
    IPAD = ('iPad',)  #
    IPHONE = ('iPhone',)  # In fact, these are IOS both, but we can diferentiate them
    WYSE = ('WYSE',)
    UNKNOWN = ('Unknown',)

    def os_name(self):
        return self.value[0].lower()

knownOss = tuple(os for os in KnownOS if os != KnownOS.UNKNOWN)

allOss = knownOss + (KnownOS.UNKNOWN,)
desktopOss = (KnownOS.LINUX, KnownOS.WINDOWS, KnownOS.MAC_OS)
mobilesODD = list(set(allOss) - set(desktopOss))


DEFAULT_OS = KnownOS.WINDOWS

class KnownBrowser(enum.Enum):
    # Known browsers
    FIREFOX = 'Firefox'
    SEAMONKEY = 'Seamonkey'
    CHROME = 'Chrome'
    CHROMIUM = 'Chromium'
    SAFARI = 'Safari'
    OPERA = 'Opera'
    IEXPLORER = 'Explorer'
    EDGE = 'Edge'
    OTHER = 'Other'

knownBrowsers = tuple(KnownBrowser)

browsersREs: typing.Dict[KnownBrowser, typing.Tuple] = {
    KnownBrowser.FIREFOX: (re.compile(r'Firefox/([0-9.]+)'),),
    KnownBrowser.SEAMONKEY: (re.compile(r'Seamonkey/([0-9.]+)'),),
    KnownBrowser.CHROME: (re.compile(r'Chrome/([0-9.]+)'),),
    KnownBrowser.CHROMIUM: (re.compile(r'Chromium/([0-9.]+)'),),
    KnownBrowser.SAFARI: (re.compile(r'Safari/([0-9.]+)'),),
    KnownBrowser.OPERA: (
        re.compile(r'OPR/([0-9.]+)'),
        re.compile(r'Opera/([0-9.]+)'),
    ),
    KnownBrowser.IEXPLORER: (
        re.compile(r';MSIE ([0-9.]+);'),
        re.compile(r'Trident/.*rv:([0-9.]+)'),
    ),
    KnownBrowser.EDGE: (re.compile(r'Edg/([0-9.]+)'),),
}

browserRules: typing.Dict[KnownBrowser, typing.Tuple] = {
    KnownBrowser.EDGE: (KnownBrowser.EDGE, ()),
    KnownBrowser.CHROME: (KnownBrowser.CHROME, (KnownBrowser.CHROMIUM, KnownBrowser.OPERA)),
    KnownBrowser.FIREFOX: (KnownBrowser.FIREFOX, (KnownBrowser.SEAMONKEY,)),
    KnownBrowser.IEXPLORER: (KnownBrowser.IEXPLORER, ()),
    KnownBrowser.CHROMIUM: (KnownBrowser.CHROMIUM, (KnownBrowser.CHROME,)),
    KnownBrowser.SAFARI: (KnownBrowser.SAFARI, (KnownBrowser.CHROME, KnownBrowser.CHROMIUM, KnownBrowser.OPERA)),
    KnownBrowser.SEAMONKEY: (KnownBrowser.SEAMONKEY, (KnownBrowser.FIREFOX,)),
    KnownBrowser.OPERA: (KnownBrowser.OPERA, ()),
}


def getOsFromUA(
    ua: typing.Optional[str],
) -> DetectedOsInfo:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = ua or KnownOS.UNKNOWN.value[0]

    res = DetectedOsInfo(os=KnownOS.UNKNOWN, browser=KnownBrowser.OTHER, version='0.0')
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
