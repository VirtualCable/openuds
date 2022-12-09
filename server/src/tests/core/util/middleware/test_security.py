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
import logging

from django.urls import reverse

from uds.core.util import config
from uds.core.util.middleware.redirect import _NO_REDIRECT

from ....utils import test


logger = logging.getLogger(__name__)


class SecurityMiddlewareTest(test.UDSTransactionTestCase):
    """
    Test actor functionality
    """
    def test_security(self) -> None:
        SecurityMiddlewareTest.add_middleware('uds.core.util.middleware.security.UDSSecurityMiddleware')
        # No trusted sources
        config.GlobalConfig.TRUSTED_SOURCES.set('')
        # Without user agent, security middleware will return forbidden (403) if not Trusted IP
        # With user agent, it will process normally (/ will redirect to index, for example, and index will return 200)
        # If user agent contains "bot" or "spider" it will return 403 in all cases
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))
        # Try secure, will redirect to index also
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

        # Remove user agent, will return 403
        self.client.set_user_agent(None)
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 403)

        # Bots also are denied
        self.client.set_user_agent('Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)')
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 403)

        # Add trusted ip, 127.0.0.1
        config.GlobalConfig.TRUSTED_SOURCES.set('127.0.0.1')
        # Bot will be denied anyway, even if trusted source
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 403)
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 403)
        
        # Emtpy user agent will be allowed from trusted source
        self.client.set_user_agent(None)
        response = self.client.get('/', secure=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))



