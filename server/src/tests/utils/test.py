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

from django.test import TestCase, TransactionTestCase
from django.test.client import Client
from django.conf import settings

from uds import models
from uds.REST.handlers import AUTH_TOKEN_HEADER
from uds.core.managers.crypto import CryptoManager


logger = logging.getLogger(__name__)

class UDSClient(Client):
    headers: typing.Dict[str, str] = {
        'HTTP_USER_AGENT': 'Testing user agent',
    }

    def __init__(
        self, enforce_csrf_checks: bool =False, raise_request_exception: bool=True, **defaults: typing.Any
    ):
        # Ensure only basic middleware are enabled.
        settings.MIDDLEWARE = [
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.locale.LocaleMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
            'uds.core.util.middleware.request.GlobalRequestMiddleware',
        ]

        # Instantiate the client and add basic user agent
        super().__init__(enforce_csrf_checks, raise_request_exception)
        # and required UDS cookie
        self.cookies['uds'] = CryptoManager().randomString(48)

    def add_header(self, name: str, value: str):
        self.headers[name] = value

    def request(self, **request: typing.Any):
        # Copy request dict
        request = request.copy()
        # Add headers
        request.update(self.headers)
        return super().request(**request)


class UDSTestCase(TestCase):
    client_class: typing.Type = UDSClient

    client: UDSClient

class UDSTransactionTestCasse(TransactionTestCase):
    client_class: typing.Type = UDSClient

    client: UDSClient
