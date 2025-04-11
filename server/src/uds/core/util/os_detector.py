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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from uds.core import types, consts

logger = logging.getLogger(__name__)


def detect_os(
    headers: collections.abc.Mapping[str, typing.Any],
) -> types.os.DetectedOsInfo:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = headers.get('User-Agent') or types.os.KnownOS.UNKNOWN.value[0]

    res = types.os.DetectedOsInfo(
        os=types.os.KnownOS.UNKNOWN, browser=types.os.KnownBrowser.OTHER, version='0.0'
    )

    # First, try to detect from Sec-Ch-Ua-Platform
    # Remember all Sec... headers are only available on secure connections
    

    if (sec_ch_ua_platform := typing.cast(str|None, headers.get('Sec-Ch-Ua-Platform'))) is not None:
        # Strip initial and final " chars if present
        sec_ch_ua_platform = sec_ch_ua_platform.strip('"')
        for os in consts.os.KNOWN_OS_LIST:
            if sec_ch_ua_platform in os.value:
                res.os = os
                break
            
    if res.os == types.os.KnownOS.UNKNOWN:
        ual = ua.lower()
        for os in consts.os.KNOWN_OS_LIST:
            for osname in os.value:
                if osname.lower() in ual:
                    res.os = types.os.KnownOS(os)
                    break

    # Try to detect browser from Sec-Ch-Ua first
    if (sec_ch_ua := typing.cast(str|None, headers.get('Sec-Ch-Ua'))) is not None:
        for browser in consts.os.KNOW_BROWSERS:
            if browser in sec_ch_ua:
                res.browser = browser
                break
    
    if res.browser == types.os.KnownBrowser.OTHER:
        # Try to detect browser from User-Agent
        found: 'None|typing.Match[str]' = None

        browser_type = None
        for browser_type, rules in consts.os.BROWSER_RULES.items():
            must_rule, must_not_rule = rules

            for must_re in consts.os.BROWSERS_RE[must_rule]:
                found = must_re.search(ua)
                if found is None:
                    continue
                # Check against no maching rules
                for must_not_re_list in must_not_rule:
                    for cre in consts.os.BROWSERS_RE[must_not_re_list]:
                        if cre.search(ua) is not None:
                            found = None
                            break
                    if found is None:
                        break
                if found is not None:
                    break
            if found is not None:
                break

        if found is not None:
            res.browser = browser_type or types.os.KnownBrowser.OTHER
            res.version = '0.0'

    logger.debug('Detected: %s %s', res.os, res.browser)

    return res
