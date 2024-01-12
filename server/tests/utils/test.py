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

from django.test import TestCase, TransactionTestCase
from django.test.client import Client, AsyncClient  # type: ignore   # Pylance does not know about AsyncClient, but it is there
from django.http.response import HttpResponse
from django.conf import settings

from uds.core.managers.crypto import CryptoManager


logger = logging.getLogger(__name__)

REST_PATH = '/uds/rest/'


class UDSHttpResponse(HttpResponse):
    """
    Custom response class to be able to access the response content
    """

    def __init__(self, content, *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self.content = content  # type: ignore  # mypy does not know about this setter
        
    def json(self) -> typing.Any:
        return super().json()   # type: ignore  # mypy does not know about this method


class UDSClientMixin:
    uds_headers: dict[str, str]
    ip_version: int = 4

    def initialize(self):
        # Ensure only basic middleware are enabled.
        settings.MIDDLEWARE = [
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.locale.LocaleMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'uds.middleware.request.GlobalRequestMiddleware',
        ]
        self.uds_headers = {
            'User-Agent': 'Testing user agent',
        }

        # Update settings security options
        settings.RSA_KEY = '-----BEGIN PRIVATE KEY-----\nMIIEvwIBADANBgkqhkiG9w0BAQEFAASCBKkwggSlAgEAAoIBAQDcANi/08cnpn04\njKW/o2G1k4SIa6dJks8DmT4MQHOWqYC46YSIIPzqGoBPcvkbDSPSFBnByo3HhMY+\nk4JHc9SUwEmHSJWDCHjt7XSXX/ryqH0QQIJtSjk9Bc+GkOU24mnbITiw7ORjp7VN\nvgFdFhjVsZM/NjX/6Y9DoCPC1mGj0O9Dd4MfCsNwUxRhhR6LdrEnpRUSVW0Ksxbz\ncTfpQjdFr86+1BeUbzqN2HDcEGhvioj+0lGPXcOZoRNYU16H7kjLNP+o+rC7f/q/\nfoOYLzDSkmzePbcG+g0Hv7K7fuLus05ZWjupOmJA9hytB1BIF4p5f4ewl05Fx2Zj\nG2LneO2fAgMBAAECggEBANDimOnh2TkDceeMWx+OsAooC3E/zbEkjBudl3UoiNcn\nD0oCpkxeDeT0zpkgz/ZoTnd7kE0Y1e73WQc3JT5UcyXdQLMLLrIgDDnT+Jx1jB5z\n7XLN3UiJbblL2BOrZYbsCJf/fgU2l08rgBBVdJP+lAvps6YUAcd+6gDKfsnSpRhU\nWBHLZde7l6vUJ2OK9ZmHaghF5E8Xx918OSUKFJfGTYL5JLTb/scdl8vQse1quWC1\nk48PPXK10vOFvYWonQpRb2cOK/PPjPXPNWzcQyQY9D1iOeFvRyLqOXYE/ZY+qDe2\nHdPGrkl67yz01nzepkWWg/ZNbMXeZZyOnZm0aXtOxtkCgYEA/Qz3mescgwrt67yh\nFrbXjUqiVf2IpbNt88CUcbY0r1EdTA9OMtOtPYNvfpyRIRfDaZJ1zAdh3CZ2/hTm\ng+VUtseKnUDCi0xIBKX3V2O8sryWt2KStTnTo6JP0T47yXvmaRu5cutgoaD9SK+r\nN5vg1D2gNLmsT8uJh1Bl/yWGC4sCgYEA3pFGgAmiywsvmsddkI+LujoQVTiqkfFg\nMHHsJFOZlhYO83g49Q11pcQ70ukT6e89Ggwy///+z19p8jJ+wGqQWQLsM6eO1utg\nnJ8wMTwk8tOEm9MnWnnWhtG9KWcgkmwOVQiesJdWa1xOqsBKGchUkugmFycKNsiG\nHUbogbJ0OL0CgYBVLIcuxKdNKGGaxlwGVDbLdQKdJQBYncN1ly2f9K9ZD1loH4K3\nsu4N1W6y1Co5VFFO+KAzs4xp2HyW2xwX6xoPh6yNb53L2zombmKJhKWgF8A3K7Or\n0jH9UwXArUzcbZrJaC6MktNss85tJ8vepNYROkjxVkm8dgrtg89BCTVMLwKBgQCW\nSSh+uoL3cdUyQV63h4ZFOIHg2cOrin52F+bpXJ3/z2NHGa30IqOHTGtM7l+o/geX\nOBeT72tC4d2rUlduXEaeJDAUbRcxnnx9JayoAkG8ygDoK3uOR2kJXkTJ2T4QQPCo\nkIp/GaGcGxdviyo+IJyjGijmR1FJTrvotwG22iZKTQKBgQCIh50Dz0/rqZB4Om5g\nLLdZn1C8/lOR8hdK9WUyPHZfJKpQaDOlNdiy9x6xD6+uIQlbNsJhlDbOudHDurfI\nghGbJ1sy1FUloP+V3JAFS88zIwrddcGEso8YMFMCE1fH2/q35XGwZEnUq7ttDaxx\nHmTQ2w37WASIUgCl2GhM25np0Q==\n-----END PRIVATE KEY-----\n'
        settings.CERTIFICATE = '-----BEGIN CERTIFICATE-----\nMIICzTCCAjYCCQCOUQEWpuEa3jANBgkqhkiG9w0BAQUFADCBqjELMAkGA1UEBhMC\nRVMxDzANBgNVBAgMBk1hZHJpZDEUMBIGA1UEBwwLQWxjb3Jjw4PCs24xHTAbBgNV\nBAoMFFZpcnR1YWwgQ2FibGUgUy5MLlUuMRQwEgYDVQQLDAtEZXZlbG9wbWVudDEY\nMBYGA1UEAwwPQWRvbGZvIEfDg8KzbWV6MSUwIwYJKoZIhvcNAQkBFhZhZ29tZXpA\ndmlydHVhbGNhYmxlLmVzMB4XDTEyMDYyNTA0MjM0MloXDTEzMDYyNTA0MjM0Mlow\ngaoxCzAJBgNVBAYTAkVTMQ8wDQYDVQQIDAZNYWRyaWQxFDASBgNVBAcMC0FsY29y\nY8ODwrNuMR0wGwYDVQQKDBRWaXJ0dWFsIENhYmxlIFMuTC5VLjEUMBIGA1UECwwL\nRGV2ZWxvcG1lbnQxGDAWBgNVBAMMD0Fkb2xmbyBHw4PCs21lejElMCMGCSqGSIb3\nDQEJARYWYWdvbWV6QHZpcnR1YWxjYWJsZS5lczCBnzANBgkqhkiG9w0BAQEFAAOB\njQAwgYkCgYEA35iGyHS/GVdWk3n9kQ+wsCLR++jd9Vez/s407/natm8YDteKksA0\nMwIvDAX722blm8PUya2NOlnum8KdyUPDOq825XERDlsIA+sTd6lb1c7w44qZ/pb+\n68mhXoRx2VJsu//+zhBkaQ1/KcugeHa4WLRIH35YLxdQDxrXS1eQWccCAwEAATAN\nBgkqhkiG9w0BAQUFAAOBgQAk+fJPpY+XvUsxR2A4SaQ8TGnE2x4PtpwCrCVzKEU9\nW2ugdXvysxkHbib3+JdA6s+lJjHs5HiMZPo/ak8adEKke+d10EU5YcUaJRRUpStY\nqQHziaqOl5Hgi75Kjskq6+tCU0Iui+s9pBg0V6y1AQsCmH2xFs7t1oEOGRFVarfF\n4Q==\n-----END CERTIFICATE-----'

    def add_header(self, name: str, value: str):
        self.uds_headers[name] = value

    def set_user_agent(self, user_agent: typing.Optional[str] = None):
        user_agent = user_agent or ''
        # Add 'HTTP_USER_AGENT' header
        self.uds_headers['User-Agent'] = user_agent

    def enable_ipv4(self):
        self.ip_version = 4

    def enable_ipv6(self):
        self.ip_version = 6

    def update_request_kwargs(self, kwargs: dict[str, typing.Any]) -> None:
        if self.ip_version == 4:
            kwargs['REMOTE_ADDR'] = '127.0.0.1'
        elif self.ip_version == 6:
            kwargs['REMOTE_ADDR'] = '::1'
            
        kwargs['headers'] = self.uds_headers

    def compose_rest_url(self, method: str) -> str:
        return f'{REST_PATH}/{method}'


class UDSClient(UDSClientMixin, Client):
    def __init__(
        self,
        enforce_csrf_checks: bool = False,
        raise_request_exception: bool = True,
        **defaults: typing.Any,
    ):
        UDSClientMixin.initialize(self)

        # Instantiate the client and add basic user agent
        super().__init__(enforce_csrf_checks, raise_request_exception)  # type: ignore  # Pyright Complains, but this is ok

        # and required UDS cookie
        self.cookies['uds'] = CryptoManager().random_string(48)

    def request(self, **request: typing.Any):
        # Copy request dict
        # request = request.copy()
        # Add META headers
        # request.update(self.uds_headers)
        return super().request(**request)

    def get(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', super().get(*args, **kwargs))

    def rest_get(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        # compose url
        return self.get(self.compose_rest_url(method), *args, **kwargs)

    def post(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', super().post(*args, **kwargs))

    def rest_post(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        # compose url
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return self.post(self.compose_rest_url(method), *args, **kwargs)

    def put(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', super().put(*args, **kwargs))

    def rest_put(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return self.put(self.compose_rest_url(method), *args, **kwargs)

    def delete(self, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return typing.cast('UDSHttpResponse', super().delete(*args, **kwargs))

    def rest_delete(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return self.delete(self.compose_rest_url(method), *args, **kwargs)


class UDSAsyncClient(UDSClientMixin, AsyncClient):
    def __init__(
        self,
        enforce_csrf_checks: bool = False,
        raise_request_exception: bool = True,
        **defaults: typing.Any,
    ):
        UDSClientMixin.initialize(self)

        # Instantiate the client and add basic user agent
        super().__init__(enforce_csrf_checks, raise_request_exception)  # type: ignore  # Coplains, but this is ok

        # and required UDS cookie
        self.cookies['uds'] = CryptoManager().random_string(48)

    async def request(self, **request: typing.Any):
        # Copy request dict
        request = request.copy()
        # Add headers
        request.update(self.uds_headers)
        return await super().request(**request)

    # pylint: disable=invalid-overridden-method
    async def get(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', await super().get(*args, **kwargs))

    async def rest_get(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        # compose url
        return await self.get(self.compose_rest_url(method), *args, **kwargs)

    # pylint: disable=invalid-overridden-method
    async def post(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', await super().post(*args, **kwargs))

    async def rest_post(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return await self.post(self.compose_rest_url(method), *args, **kwargs)

    # pylint: disable=invalid-overridden-method
    async def put(self, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return typing.cast('UDSHttpResponse', await super().put(*args, **kwargs))

    async def rest_put(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        kwargs['content_type'] = kwargs.get('content_type', 'application/json')
        return await self.put(self.compose_rest_url(method), *args, **kwargs)

    # pylint: disable=invalid-overridden-method
    async def delete(self, *args, **kwargs) -> 'UDSHttpResponse':
        self.update_request_kwargs(kwargs)
        return typing.cast('UDSHttpResponse', await super().delete(*args, **kwargs))

    async def rest_delete(self, method: str, *args, **kwargs) -> 'UDSHttpResponse':
        # compose url
        return await self.delete(self.compose_rest_url(method), *args, **kwargs)


class UDSTestCaseMixin:
    client_class: typing.Type = UDSClient
    async_client_class: typing.Type = UDSAsyncClient

    client: UDSClient
    async_client: UDSAsyncClient

    @staticmethod
    def add_middleware(middleware: str) -> None:
        if middleware not in settings.MIDDLEWARE:
            settings.MIDDLEWARE.append(middleware)

    @staticmethod
    def remove_middleware(middleware: str) -> None:
        # Remove middleware from settings, if present
        try:
            settings.MIDDLEWARE.remove(middleware)
        except ValueError:
            pass  # Not present


class UDSTestCase(UDSTestCaseMixin, TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        setupClass(cls)  # The one local to this module


class UDSTransactionTestCase(UDSTestCaseMixin, TransactionTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        setupClass(cls)


# pylint: disable=unused-argument
def setupClass(cls: typing.Union[type[UDSTestCase], type[UDSTransactionTestCase]]) -> None:
    # Nothing right now
    pass
