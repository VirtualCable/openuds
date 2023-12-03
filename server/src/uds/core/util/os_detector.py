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



def getOsFromUA(
    ua: typing.Optional[str],
) -> types.os.DetectedOsInfo:
    """
    Basic OS Client detector (very basic indeed :-))
    """
    ua = ua or types.os.KnownOS.UNKNOWN.value[0]

    res = types.os.DetectedOsInfo(os=types.os.KnownOS.UNKNOWN, browser=types.os.KnownBrowser.OTHER, version='0.0')
    found: bool = False
    for os in consts.os.KNOWN_OS_LIST:
        if found:
            break
        for osName in os.value:
            if osName in ua:
                res = res._replace(os=os)
                found = True
                break

    match = None

    ruleKey, ruleValue = None, None
    for ruleKey, ruleValue in consts.os.browserRules.items():
        must, mustNot = ruleValue

        for mustRe in consts.os.browsersREs[must]:
            match = mustRe.search(ua)
            if match is None:
                continue
            # Check against no maching rules
            for mustNotREs in mustNot:
                for cre in consts.os.browsersREs[mustNotREs]:
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
