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
import logging
from unittest import mock

from django.urls import reverse

from uds.core import consts
from uds.core.util import config
from uds.middleware import request

from ..utils.web import test


if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)


class GlobalRequestMiddlewareTest(test.WEBTestCase):
    """
    Test actor functionality
    """

    def test_global_request_no_login_ipv4(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv4()

        response = self.client.get('/', secure=False)
        req = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = False, not logged in
        self.assertEqual(req.session.get(consts.auth.SESSION_AUTHORIZED_KEY), False)

        # Ensure ip, and ip_proxy are set and both are the same, 127.0.0.1
        self.assertEqual(req.ip, '127.0.0.1')
        self.assertEqual(req.ip_proxy, '127.0.0.1')
        self.assertEqual(req.ip_version, 4)

        # Ensure user is not set
        self.assertEqual(req.user, None)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_no_login_ipv6(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv6()

        response = self.client.get('/', secure=False)
        req = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = False, not logged in
        self.assertEqual(req.session.get(consts.auth.SESSION_AUTHORIZED_KEY), False)

        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(req.ip, '::1')
        self.assertEqual(req.ip_proxy, '::1')
        self.assertEqual(req.ip_version, 6)

        # Ensure user is not set
        self.assertEqual(req.user, None)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_login_ipv4(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv4()

        user = self.login(as_admin=False)

        response = self.client.get('/', secure=False)
        req = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = True, logged in
        self.assertEqual(req.session.get(consts.auth.SESSION_AUTHORIZED_KEY), True)

        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(req.ip, '127.0.0.1')
        self.assertEqual(req.ip_proxy, '127.0.0.1')
        self.assertEqual(req.ip_version, 4)

        # Ensure user is correct
        self.assertEqual(req.user.uuid, user.uuid)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_global_request_login_ipv6(self) -> None:
        GlobalRequestMiddlewareTest.add_middleware(
            'uds.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv6()

        user = self.login(as_admin=False)

        response = self.client.get('/', secure=False)
        req = typing.cast('ExtendedHttpRequestWithUser', response.wsgi_request)
        # session[AUTHORIZED_KEY] = True, logged in
        self.assertEqual(req.session.get(consts.auth.SESSION_AUTHORIZED_KEY), True)

        # Ensure ip, and ip_proxy are set and both are the same,
        self.assertEqual(req.ip, '::1')
        self.assertEqual(req.ip_proxy, '::1')
        self.assertEqual(req.ip_version, 6)

        # Ensure user is correct
        self.assertEqual(req.user.uuid, user.uuid)
        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_no_middleware(self) -> None:
        # Ensure GlobalRequestMiddleware is not present
        GlobalRequestMiddlewareTest.remove_middleware(
            'uds.middleware.request.GlobalRequestMiddleware'
        )
        self.client.enable_ipv4()

        response = self.client.get('/', secure=False)
        req = response.wsgi_request
        # session[AUTHORIZED_KEY] is not present
        self.assertEqual(consts.auth.SESSION_AUTHORIZED_KEY in req.session, False)

        # ip is not present, nor ip_proxy or ip_version
        self.assertEqual(hasattr(req, 'ip'), False)
        self.assertEqual(hasattr(req, 'ip_proxy'), False)
        self.assertEqual(hasattr(req, 'ip_version'), False)

        # Also, user is not present
        self.assertEqual(hasattr(req, 'user'), False)

        # And redirects to index
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('page.index'))

    def test_detect_ips_no_proxy(self) -> None:
        req = mock.Mock()
        # Use an ipv4 and an ipv6 address
        for ip in ['192.168.128.128', '2001:db8:85a3:8d3:1319:8a2e:370:7348']:
            req.META = {
                'REMOTE_ADDR': ip,
            }
            request._fill_ips(req)  # pylint: disable=protected-access
            self.assertEqual(req.ip, ip)
            self.assertEqual(req.ip_proxy, ip)
            self.assertEqual(req.ip_version, 4 if '.' in ip else 6)

    def test_detect_ips_proxy(self) -> None:
        config.GlobalConfig.BEHIND_PROXY.set(True)
        req = mock.Mock()
        # Use an ipv4 and an ipv6 address
        for client_ip in ['192.168.128.128', '2001:db8:85a3:8d3:1319:8a2e:370:7348']:
            for proxy in ['192.168.200.200', '2001:db8:85a3:8d3:1319:8a2e:370:7349']:
                for with_nginx in [True, False]:
                    # Remote address is not included by NGINX, it's on the X-Forwarded-For header
                    if with_nginx is False:
                        req.META = {
                            'REMOTE_ADDR': proxy,
                            'HTTP_X_FORWARDED_FOR': client_ip,
                        }
                    else:
                        req.META = {'HTTP_X_FORWARDED_FOR': f'{client_ip},{proxy}'}

                    request._fill_ips(req)  # pylint: disable=protected-access
                    self.assertEqual(
                        req.ip, client_ip, "Failed for {}".format(req.META)
                    )
                    self.assertEqual(
                        req.ip_proxy, client_ip, "Failed for {}".format(req.META)
                    )
                    self.assertEqual(
                        req.ip_version,
                        4 if '.' in client_ip else 6,
                        "Failed for {}".format(req.META),
                    )

    def test_detect_ips_proxy_chained(self) -> None:
        config.GlobalConfig.BEHIND_PROXY.set(True)
        req = mock.Mock()
        # Use an ipv4 and an ipv6 address
        for client_ip in ['192.168.128.128', '2001:db8:85a3:8d3:1319:8a2e:370:7348']:
            for first_proxy in [
                '192.168.200.200',
                '2001:db8:85a3:8d3:1319:8a2e:370:7349',
            ]:
                for second_proxy in [
                    '192.168.201.201',
                    '2001:db8:85a3:8d3:1319:8a2e:370:7350',
                ]:
                    for with_nginx in [True, False]:
                        x_forwarded_for = '{}, {}'.format(client_ip, first_proxy)
                        if with_nginx is False:
                            req.META = {
                                'REMOTE_ADDR': client_ip,
                                'HTTP_X_FORWARDED_FOR': x_forwarded_for,
                            }
                        else:
                            req.META = {
                                'HTTP_X_FORWARDED_FOR': "{}, {}".format(
                                    x_forwarded_for, second_proxy
                                ),
                            }

                        request._fill_ips(req)
                        self.assertEqual(req.ip, first_proxy)
                        self.assertEqual(req.ip_proxy, client_ip)
                        self.assertEqual(req.ip_version, 4 if '.' in first_proxy else 6)
