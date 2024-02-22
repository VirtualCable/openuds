# -*- coding: utf-8 -*-

#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import re
import typing
import collections.abc

from uds.core import types


KNOWN_OS_LIST: typing.Final[tuple[types.os.KnownOS, ...]] = tuple(
    os for os in types.os.KnownOS if os != types.os.KnownOS.UNKNOWN
)

ALL_OS_LIST: typing.Final[tuple[types.os.KnownOS, ...]] = KNOWN_OS_LIST + (types.os.KnownOS.UNKNOWN,)
DESKTOP_OSS: typing.Final[tuple[types.os.KnownOS, ...]] = (
    types.os.KnownOS.LINUX,
    types.os.KnownOS.WINDOWS,
    types.os.KnownOS.MAC_OS,
)
MOBILE_OS_LIST: typing.Final[tuple[types.os.KnownOS, ...]] = tuple(set(ALL_OS_LIST) - set(DESKTOP_OSS))


DEFAULT_OS: typing.Final[types.os.KnownOS] = types.os.KnownOS.WINDOWS


KNOW_BROWSERS: typing.Final[tuple[types.os.KnownBrowser, ...]] = tuple(types.os.KnownBrowser)

BROWSERS_RE: dict[types.os.KnownBrowser, tuple[typing.Pattern[str], ...]] = {
    types.os.KnownBrowser.FIREFOX: (re.compile(r'Firefox/([0-9.]+)'),),
    types.os.KnownBrowser.SEAMONKEY: (re.compile(r'Seamonkey/([0-9.]+)'),),
    types.os.KnownBrowser.CHROME: (re.compile(r'Chrome/([0-9.]+)'),),
    types.os.KnownBrowser.CHROMIUM: (re.compile(r'Chromium/([0-9.]+)'),),
    types.os.KnownBrowser.SAFARI: (re.compile(r'Safari/([0-9.]+)'),),
    types.os.KnownBrowser.OPERA: (
        re.compile(r'OPR/([0-9.]+)'),
        re.compile(r'Opera/([0-9.]+)'),
    ),
    types.os.KnownBrowser.IEXPLORER: (
        re.compile(r';MSIE ([0-9.]+);'),
        re.compile(r'Trident/.*rv:([0-9.]+)'),
    ),
    types.os.KnownBrowser.EDGE: (re.compile(r'Edg/([0-9.]+)'),),
}

BROWSER_RULES: dict[types.os.KnownBrowser, tuple] = {
    types.os.KnownBrowser.EDGE: (types.os.KnownBrowser.EDGE, ()),
    types.os.KnownBrowser.CHROME: (
        types.os.KnownBrowser.CHROME,
        (types.os.KnownBrowser.CHROMIUM, types.os.KnownBrowser.OPERA),
    ),
    types.os.KnownBrowser.FIREFOX: (types.os.KnownBrowser.FIREFOX, (types.os.KnownBrowser.SEAMONKEY,)),
    types.os.KnownBrowser.IEXPLORER: (types.os.KnownBrowser.IEXPLORER, ()),
    types.os.KnownBrowser.CHROMIUM: (types.os.KnownBrowser.CHROMIUM, (types.os.KnownBrowser.CHROME,)),
    types.os.KnownBrowser.SAFARI: (
        types.os.KnownBrowser.SAFARI,
        (types.os.KnownBrowser.CHROME, types.os.KnownBrowser.CHROMIUM, types.os.KnownBrowser.OPERA),
    ),
    types.os.KnownBrowser.SEAMONKEY: (types.os.KnownBrowser.SEAMONKEY, (types.os.KnownBrowser.FIREFOX,)),
    types.os.KnownBrowser.OPERA: (types.os.KnownBrowser.OPERA, ()),
}

# Max wait time for guest shutdown
MAX_GUEST_SHUTDOWN_WAIT: typing.Final[int] = 90  # Seconds
