# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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

from uds.core import types
from uds.core.util import os_detector

from tests.utils.test import UDSTestCase


logger = logging.getLogger(__name__)


class OsDetectorTest(UDSTestCase):
    def test_detect_chromeos(self) -> None:
        user_agents = [
            'Mozilla/5.0 (X11; CrOS x86_64 16181.47.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.130 Safari/537.36',
            'Mozilla/5.0 (X11; CrOS armv7l 16181.47.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.130 Safari/537.36',
            'Mozilla/5.0 (X11;CrOS aarch64 16181.47.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.6998.130 Safari/537.36',
        ]
        for user_agent in user_agents:
            assert (
                os_detector.detect_os(
                    headers={
                        'User-Agent': user_agent,
                    }
                ).os
                == types.os.KnownOS.CHROME_OS
            ), f'Failed to detect ChromeOS for {user_agent}'

    def test_detect_chromeos_ssl_headers(self) -> None:
        """
        Test detection of ChromeOS using SSL headers, including fallback to User-Agent
        when Sec-Ch-Ua-Platform contains an unexpected value.
        """
        headers = {
            'Content-Length': '',
            'Content-Type': 'text/plain',
            'Host': '172.27.0.1:8443',
            'Connection': 'keep-alive',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Chrome OS"',
            'Dnt': '1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-User': '?1',
            'Sec-Fetch-Dest': 'document',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'es,en;q=0.9',
            'Cookie': 'sessionid=pfif34l989sw010h5qtmrzb6wd71ggch; uds=egOiL4Eg3sppQL5r7VHLgfwI0qq9Kdow5w4vZdnvYMPmScxz',
            'Sec-Gpc': '1',
        }
        assert os_detector.detect_os(headers).os == types.os.KnownOS.CHROME_OS, 'Failed to detect ChromeOS'

    def test_fallback_to_user_agent(self) -> None:
        """
        Test that detection falls back to User-Agent when Sec-Ch-Ua-Platform contains an unexpected value.
        """
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
            'Sec-Ch-Ua-Platform': '"UnexpectedPlatform"',
        }
        assert os_detector.detect_os(headers).os == types.os.KnownOS.CHROME_OS, 'Fallback to User-Agent failed'
        # Setting Sec-Ch-Ua-Platform to an unexpected value to ensure fallback to User-Agent detection
        headers['Sec-Ch-Ua-Platform'] = '"UnknownPlatform"'
        assert os_detector.detect_os(headers).os == types.os.KnownOS.CHROME_OS, 'Failed to detect ChromeOS'
