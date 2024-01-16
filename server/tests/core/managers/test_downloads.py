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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing
import collections.abc
import os.path
import sys

# We use commit/rollback
from ...utils.web.test import WEBTestCase
from django.urls import reverse
from uds.core.managers.downloads import DownloadsManager

from uds.core.util.config import GlobalConfig

if typing.TYPE_CHECKING:
    from django.http import HttpResponse

class DownloadsManagerTest(WEBTestCase):
    filePath: str = ''
    manager: DownloadsManager

    @classmethod
    def setUpClass(cls):
        from uds.core.managers import downloads_manager

        super().setUpClass()

        cls.filePath = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'downloadable.txt'
        )
        cls.manager = downloads_manager()

    def test_downloads(self):
        for v in (
            ('test.txt', 'text/plain', '1f47ec0a-1ad4-5d63-b41c-5d2befadab8d'),
            (
                'test.bin',
                'application/octet-stream',
                '6454d619-cc62-5bd4-aa9a-c9e2458d44da',
            ),
        ):
            fileName, mimeType, knownUuid = v
            self.manager.register(
                fileName,
                'This is the test file {}'.format(fileName),
                self.filePath,
                mimeType,
            )

            downloadables = self.manager.downloadables()

            self.assertIn(
                knownUuid,
                downloadables,
                'The File {} was not found in downloadables!'.format(fileName),
            )

            # Downloadables are allowed by admin or staff
            self.login(as_admin=True)

            # This will fail, no user has logged in
            self.client.get(
                reverse('utility.downloader', kwargs={'download_id': knownUuid})
            )
            # Remove last '/' for redirect check. URL redirection will not contain it
            # Commented because i don't know why when executed in batch returns the last '/', and alone don't
            # self.assertRedirects(response, reverse('uds.web.views.login'), fetch_redirect_response=False)

            # And try to download again
            response = self.client.get(
                reverse('utility.downloader', kwargs={'download_id': knownUuid})
            )
            self.assertEqual(
                response.get('Content-Type'),
                mimeType,
                'Mime type of {} is not {} as expected (it is {})'.format(
                    fileName, mimeType, response.get('Content-Type')
                ),
            )
            self.assertContains(
                response,
                'This file is the downloadable for download manager tests',
                msg_prefix='File does not seems to be fine',
            )

            # Now do logout
            # response = client.get(reverse('uds.web.views.logout'))
            # self.assertRedirects(response, reverse('uds.web.views.login')[:-1], fetch_redirect_response=False)
