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
from uds.core.auths.auth import AUTHORIZED_KEY

from ....utils.web import test


if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class GlobalRequestMiddlewareTest(test.WEBTestCase):
    """
    Test actor functionality
    """

    def test_global_request_no_login_ipv4(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.core.util.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv4()

        response = self.client.get('/', secure=False)
        request = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = False, not logged in
        self.assertEqual(request.session.get(AUTHORIZED_KEY), False)

        # Ensure ip, and ip_proxy are set and both are the same, 127.0.0.1
        self.assertEqual(request.ip, '127.0.0.1')
        self.assertEqual(request.ip_proxy, '127.0.0.1')
        self.assertEqual(request.ip_version, 4)

        # Ensure user is not set
        self.assertEqual(request.user, None)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_no_login_ipv6(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.core.util.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv6()

        response = self.client.get('/', secure=False)
        request = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = False, not logged in
        self.assertEqual(request.session.get(AUTHORIZED_KEY), False)
        
        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(request.ip, '::1')
        self.assertEqual(request.ip_proxy, '::1')
        self.assertEqual(request.ip_version, 6)

        # Ensure user is not set
        self.assertEqual(request.user, None)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_login_ipv4(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.core.util.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv4()

        user = self.login(as_admin=False)

        response = self.client.get('/', secure=False)
        request = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = True, logged in
        self.assertEqual(request.session.get(AUTHORIZED_KEY), True)

        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(request.ip, '127.0.0.1')
        self.assertEqual(request.ip_proxy, '127.0.0.1')
        self.assertEqual(request.ip_version, 4)

        # Ensure user is correct
        self.assertEqual(request.user.uuid, user.uuid)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_login_ipv6(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.core.util.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv6()

        user = self.login(as_admin=False)

        response = self.client.get('/', secure=False)
        request = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = True, logged in
        self.assertEqual(request.session.get(AUTHORIZED_KEY), True)

        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(request.ip, '::1')
        self.assertEqual(request.ip_proxy, '::1')
        self.assertEqual(request.ip_version, 6)

        # Ensure user is correct
        self.assertEqual(request.user.uuid, user.uuid)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_no_middleware(self) -> None:
        # Ensure GlobalRequestMiddleware is not present
        GlobalRequestMiddlewareTest.remove_middleware('uds.core.util.middleware.request.GlobalRequestMiddleware')
        self.client.enable_ipv4()

        response = self.client.get('/', secure=False)
        request = response.wsgi_request
        # session[AUTHORIZED_KEY] is not present
        self.assertEqual(AUTHORIZED_KEY in request.session, False)

        # ip is not present, nor ip_proxy or ip_version
        self.assertEqual(hasattr(request, 'ip'), False)
        self.assertEqual(hasattr(request, 'ip_proxy'), False)
        self.assertEqual(hasattr(request, 'ip_version'), False)
    
        # Also, user is not present
        self.assertEqual(hasattr(request, 'user'), False)

        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))


