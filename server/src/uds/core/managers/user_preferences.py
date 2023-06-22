# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
# This module is deprecated and probably will be removed soon

import logging
import typing

logger = logging.getLogger(__name__)

class CommonPrefs:
    SZ_PREF = 'screenSize'
    SZ_640x480 = '1'
    SZ_800x600 = '2'
    SZ_1024x768 = '3'
    SZ_1366x768 = '4'
    SZ_1920x1080 = '5'
    SZ_FULLSCREEN = 'F'

    DEPTH_PREF = 'screenDepth'
    DEPTH_8 = '1'
    DEPTH_16 = '2'
    DEPTH_24 = '3'
    DEPTH_32 = '4'

    BYPASS_PREF = 'bypassPluginDetection'

    @staticmethod
    def getWidthHeight(size: str) -> typing.Tuple[int, int]:
        """
        Get width based on screenSizePref value
        """
        return {
            CommonPrefs.SZ_640x480: (640, 480),
            CommonPrefs.SZ_800x600: (800, 600),
            CommonPrefs.SZ_1024x768: (1024, 768),
            CommonPrefs.SZ_1366x768: (1366, 768),
            CommonPrefs.SZ_1920x1080: (1920, 1080),
            CommonPrefs.SZ_FULLSCREEN: (-1, -1),
        }.get(size, (1024, 768))

    @staticmethod
    def getDepth(depth: str) -> int:
        """
        Get depth based on depthPref value
        """
        return {
            CommonPrefs.DEPTH_8: 8,
            CommonPrefs.DEPTH_16: 16,
            CommonPrefs.DEPTH_24: 24,
            CommonPrefs.DEPTH_32: 32,
        }.get(depth, 24)
