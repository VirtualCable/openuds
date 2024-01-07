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
import collections.abc

from uds.core import types, consts

logger = logging.getLogger(__name__)


def detect_os(
    headers: collections.abc.Mapping[str, typing.Any],
) -> types.os.DetectedOsInfo:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = (headers.get('User-Agent') or types.os.KnownOS.UNKNOWN.value[0])

    res = types.os.DetectedOsInfo(
        os=types.os.KnownOS.UNKNOWN, browser=types.os.KnownBrowser.OTHER, version='0.0'
    )

    # First, try to detect from Sec-Ch-Ua-Platform
    # Remember all Sec... headers are only available on secure connections
    sec_ch_ua_platform = headers.get('Sec-Ch-Ua-Platform')
    found = types.os.KnownOS.UNKNOWN

    if sec_ch_ua_platform is not None:
        # Strip initial and final " chars if present
        sec_ch_ua_platform = sec_ch_ua_platform.strip('"')
        for os in consts.os.KNOWN_OS_LIST:
            if sec_ch_ua_platform in os.value:
                found = os
                break
    else:  # Try to detect from User-Agent
        ual = ua.lower()
        for os in consts.os.KNOWN_OS_LIST:
            if os.os_name().lower() in ual:
                found = os
                break

    # If we found a known OS, store it
    if found != types.os.KnownOS.UNKNOWN:
        res.os = found

    # Try to detect browser from Sec-Ch-Ua first
    sec_ch_ua = headers.get('Sec-Ch-Ua')
    if sec_ch_ua is not None:
        for browser in consts.os.known_browsers:
            if browser in sec_ch_ua:
                res.browser = browser
                break
    else:
        # Try to detect browser from User-Agent
        match = None

        ruleKey, ruleValue = None, None
        for ruleKey, ruleValue in consts.os.browser_rules.items():
            must, mustNot = ruleValue

            for mustRe in consts.os.browsers_re[must]:
                match = mustRe.search(ua)
                if match is None:
                    continue
                # Check against no maching rules
                for mustNotREs in mustNot:
                    for cre in consts.os.browsers_re[mustNotREs]:
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
            res.browser = ruleKey or types.os.KnownBrowser.OTHER
            res.version = match.groups(1)[0]

    logger.debug('Detected: %s %s', res.os, res.browser)

    return res
