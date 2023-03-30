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
import logging

from django.urls import reverse

from uds.core.util import config
from uds.core.managers.crypto import CryptoManager

from ..utils import test


logger = logging.getLogger(__name__)


class RedirectMiddlewareTest(test.UDSTransactionTestCase):
    """
    Test client functionality
    """
    def test_redirect(self):
        RedirectMiddlewareTest.add_middleware('uds.middleware.redirect.RedirectMiddleware')
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://testserver/')
        # Try secure, will redirect to index
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

        # Try several urls, random. Unsecure will redirect, secure will not
        for _ in range(32):
            url = f'/{CryptoManager().randomString(32)}'
            response = self.client.get(url, secure=False)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.url, f'https://testserver{url}')
            response = self.client.get(url, secure=True)
            self.assertEqual(response.status_code, 404) # Not found
