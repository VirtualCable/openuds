# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import string
import random
import typing

from django.test import SimpleTestCase
from django.test.client import Client
from django.conf import settings

from uds.core.managers.crypto import CryptoManager
from uds.REST.handlers import AUTH_TOKEN_HEADER

# constants
# String chars to use in random strings
STRING_CHARS = string.ascii_letters + string.digits + '_'
# Invalid string chars
STRING_CHARS_INVALID = '!@#$%^&*()_+=-[]{}|;\':",./<>? '
# String chars with invalid chars to use in random strings
STRING_CHARS_WITH_INVALID = STRING_CHARS + STRING_CHARS_INVALID


def getClient() -> Client:
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
    client = Client(HTTP_USER_AGENT='Testing user agent')
    # and required UDS cookie
    client.cookies['uds'] = CryptoManager().randomString(48)

    return client


# Calls REST login
def rest_login(
    caller: SimpleTestCase,
    client: Client,
    auth_id: str,
    username: str,
    password: str,
    expectedResponseCode: int = 200,
    errorMessage: typing.Optional[str] = None,
) -> typing.Mapping[str, typing.Any]:
    response = client.post(
        '/uds/rest/auth/login',
        {
            'auth_id': auth_id,
            'username': username,
            'password': password,
        },
        content_type='application/json',
    )

    caller.assertEqual(
        response.status_code,
        expectedResponseCode,
        'Login from {}'.format(errorMessage or caller.__class__.__name__),
    )

    if response.status_code == 200:
        return response.json()

    return {}


def rest_logout(caller: SimpleTestCase, client: Client, auth_token: str) -> None:
    response = client.get(
        '/uds/rest/auth/logout',
        content_type='application/json',
        **{AUTH_TOKEN_HEADER: auth_token}
    )
    caller.assertEqual(response.status_code, 200, 'Logout')
    caller.assertEqual(response.json(), {'result': 'ok'}, 'Logout')


def random_string_generator(size: int = 6, chars: typing.Optional[str] = None) -> str:
    chars = chars or STRING_CHARS
    return ''.join(
        random.choice(chars)  # nosec: Not used for cryptography, just for testing
        for _ in range(size)
    )


def random_ip_generator() -> str:
    return '.'.join(
        str(
            random.randint(0, 255)  # nosec: Not used for cryptography, just for testing
        )  
        for _ in range(4)
    )


def random_mac_generator() -> str:
    return ':'.join(random_string_generator(2, '0123456789ABCDEF') for _ in range(6))
