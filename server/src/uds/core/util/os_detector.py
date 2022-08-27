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

from .tools import DictAsObj

logger = logging.getLogger(__name__)


class KnownOS(enum.Enum):
    Linux = ('Linux', 'armv7l')
    ChromeOS = ('CrOS',)
    WindowsPhone = ('Windows Phone',)
    Windows = ('Windows',)
    Macintosh = ('Mac',)
    Android = ('Android',)
    iPad = ('iPad',)  #
    iPhone = ('iPhone',)  # In fact, these are IOS both, but we can diferentiate it...
    WYSE = ('WYSE',)
    Unknown = ('Unknown',)


knownOss = (
    KnownOS.WindowsPhone,
    KnownOS.Android,
    KnownOS.Linux,
    KnownOS.Windows,
    KnownOS.iPad,
    KnownOS.iPhone,
    KnownOS.Macintosh,
    KnownOS.ChromeOS,
    KnownOS.WYSE,
)  # Android is linux also, so it is cheched on first place

allOss = knownOss + (KnownOS.Unknown,)
desktopOss = (KnownOS.Linux, KnownOS.Windows, KnownOS.Macintosh)
mobilesODD = list(set(allOss) - set(desktopOss))


DEFAULT_OS = KnownOS.Windows

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

browsersREs: typing.Dict[str, typing.Tuple] = {
    Firefox: (re.compile(r'Firefox/([0-9.]+)'),),
    Seamonkey: (re.compile(r'Seamonkey/([0-9.]+)'),),
    Chrome: (re.compile(r'Chrome/([0-9.]+)'),),
    Chromium: (re.compile(r'Chromium/([0-9.]+)'),),
    Safari: (re.compile(r'Safari/([0-9.]+)'),),
    Opera: (
        re.compile(r'OPR/([0-9.]+)'),
        re.compile(r'Opera/([0-9.]+)'),
    ),
    IExplorer: (
        re.compile(r';MSIE ([0-9.]+);'),
        re.compile(r'Trident/.*rv:([0-9.]+)'),
    ),
}

browserRules: typing.Dict[str, typing.Tuple] = {
    Chrome: (Chrome, (Chromium, Opera)),
    Firefox: (Firefox, (Seamonkey,)),
    IExplorer: (IExplorer, ()),
    Chromium: (Chromium, (Chrome,)),
    Safari: (Safari, (Chrome, Chromium, Opera)),
    Seamonkey: (Seamonkey, (Firefox,)),
    Opera: (Opera, ()),
}


def getOsFromUA(
    ua: typing.Optional[str],
) -> DictAsObj:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = ua or KnownOS.Unknown.value[0]

    res = DictAsObj({'OS': KnownOS.Unknown, 'Version': '0.0', 'Browser': 'unknown'})
    found: bool = False
    for os in knownOss:
        if found:
            break
        for osName in os.value:
            if osName in ua:
                res.OS = os  # type: ignore
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
            # Check against no machin rules
            for mustNotREs in mustNot:
                for cre in browsersREs[mustNotREs]:
                    if cre.search(typing.cast(str, ua)) is not None:
                        match = None
                        break
                if match is None:
                    break
            if match is not None:
                break
        if match is not None:
            break

    if match is not None:
        res.Browser = ruleKey  # type: ignore
        res.Version = match.groups(1)[0]  # type: ignore

    return res
