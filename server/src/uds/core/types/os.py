# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import dataclasses
import enum


@dataclasses.dataclass
class DetectedOsInfo:
    os: 'KnownOS'
    browser: 'KnownBrowser'
    version: str


class KnownOS(enum.Enum):
    LINUX = ('Linux',)  # previously got 'armv7l'
    CHROME_OS = ('CrOS','Chrome OS',)
    WINDOWS_PHONE = ('Windows Phone',)
    WINDOWS = ('Windows',)
    MAC_OS = ('MacOsX', 'MacOs', 'Mac Os X', 'macOS')  # Previous was only "Mac"
    ANDROID = ('Android',)
    IPAD = ('iPad',)  #
    IPHONE = ('iPhone',)  # In fact, these are IOS both, but we can diferentiate them
    WYSE = ('WYSE',)
    UNKNOWN = ('Unknown',)

    def os_name(self) -> str:
        return self.value[0].lower()

    def db_value(self) -> str:
        """
        Returns the value to be stored in the database.
        This values are used so we can keep the database values even if we change the enum values.
        
        Returns:
        
            str: The value to be stored in the database.
        """
        return {
            'Linux': 'Linux',
            'CrOS': 'ChromeOS',
            'Windows Phone': 'WindowsPhone',
            'Windows': 'Windows',
            'MacOsX': 'Macintosh',
            'Android': 'Android',
            'iPad': 'iPad',
            'iPhone': 'iPhone',
            'WYSE': 'WYSE',
            'Unknown': 'Unknown',
        }[self.value[0]]

    def __str__(self) -> str:
        return self.os_name()


# Order is important here, as we will use the first match
class KnownBrowser(enum.StrEnum):
    # Known browsers
    FIREFOX = 'Firefox'
    SEAMONKEY = 'Seamonkey'
    EDGE = 'Microsoft Edge'
    SAFARI = 'Safari'
    OPERA = 'Opera'
    CHROME = 'Chrome'
    CHROMIUM = 'Chromium'
    IEXPLORER = 'Explorer'
    OTHER = 'Other'
