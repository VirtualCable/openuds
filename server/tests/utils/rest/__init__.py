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
import random
import typing
import collections.abc

from django.test import SimpleTestCase
from django.test.client import Client

from uds.core import consts

# Not used, allows "rest.test" or "rest.assertions"
from . import test  # pylint: disable=unused-import
from . import assertions  # pylint: disable=unused-import

from .. import generators


# Calls REST login
def login(
    caller: SimpleTestCase,
    client: Client,
    auth_id: str,
    username: str,
    password: str,
    expectedResponseCode: int = 200,
    errorMessage: typing.Optional[str] = None,
) -> collections.abc.Mapping[str, typing.Any]:
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
        f'Login from {errorMessage or caller.__class__.__name__}',
    )

    if response.status_code == 200:
        return response.json()

    return {}


def logout(caller: SimpleTestCase, client: Client) -> None:
    response = client.get(
        '/uds/rest/auth/logout',
        content_type='application/json',
    )
    caller.assertEqual(response.status_code, 200, f'Logout Result: {response.content}')
    caller.assertEqual(response.json(), {'result': 'ok'}, 'Logout Result: {response.content}')


# Rest related utils for fixtures


# Just a holder for a type, to indentify uuids
# pylint: disable=too-few-public-methods
class uuid_type:
    pass


RestFieldType = tuple[str, typing.Union[typing.Type[typing.Any], tuple[str, ...]]]
RestFieldReference = typing.Final[list[RestFieldType]]


# pylint: disable=too-many-return-statements
def random_value(
    field_type: typing.Union[typing.Type[typing.Any], tuple[str, ...]],
    value: typing.Any = None,
) -> typing.Any:
    if value is not None and value != 'fixme':
        return value

    if field_type in [str, typing.Optional[str]]:
        return generators.random_utf8_string()
    if field_type in [bool, typing.Optional[bool]]:
        return random.choice([True, False])  # nosec
    if field_type in [int, typing.Optional[int]]:
        return generators.random_int()
    if field_type in [uuid_type, typing.Optional[uuid_type]]:
        return generators.random_uuid()
    if isinstance(field_type, tuple):
        return random.choice(field_type)  # nosec
    if field_type == list[str]:
        return [generators.random_string() for _ in range(generators.random_int(1, 10))]
    if field_type == list[uuid_type]:
        return [generators.random_uuid() for _ in range(generators.random_int(1, 10))]
    if field_type == list[int]:
        return [generators.random_int() for _ in range(generators.random_int(1, 10))]
    if field_type == list[bool]:
        return [random.choice([True, False]) for _ in range(generators.random_int(1, 10))]  # nosec: test values
    if field_type == list[tuple[str, str]]:
        return [
            (generators.random_utf8_string(), generators.random_utf8_string())
            for _ in range(generators.random_int(1, 10))
        ]

    return None


class RestStruct:
    def __init__(self, **kwargs: typing.Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def as_dict(self, **kwargs: typing.Any) -> dict[str, typing.Any]:
        # Use kwargs to override values
        res = {k: kwargs.get(k, getattr(self, k)) for k in self.__annotations__}  # pylint: disable=no-member
        # Remove None values for optional fields
        return {
            k: v
            for k, v in res.items()
            if v is not None
            or self.__annotations__[k]  # pylint: disable=no-member
            not in (
                typing.Optional[str],
                typing.Optional[bool],
                typing.Optional[int],
                typing.Optional[uuid_type],
            )
        }

    @classmethod
    def random_create(cls, **kwargs: typing.Any) -> 'RestStruct':
        # Use kwargs to override values
        # Extract type from annotations
        return cls(**{k: random_value(v, kwargs.get(k, None)) for k, v in cls.__annotations__.items()})
