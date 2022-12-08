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
import datetime
import logging
import typing
import asyncio

from django.utils.decorators import sync_and_async_middleware
from django.http import HttpResponseForbidden
from django.utils import timezone

from uds.core.util import os_detector as OsDetector
from uds.core.util.config import GlobalConfig
from uds.core.auths.auth import (
    AUTHORIZED_KEY,
    EXPIRY_KEY,
    ROOT_ID,
    USER_KEY,
    getRootUser,
    webLogout,
)
from uds.models import User

if typing.TYPE_CHECKING:
    from django.http import HttpResponse
    from uds.core.util.request import ExtendedHttpRequest


logger = logging.getLogger(__name__)

# How often to check the requests cache for stuck objects
CHECK_SECONDS = 3600 * 24  # Once a day is more than enough

RequestMiddelwareProcessorType = typing.Callable[
    ['ExtendedHttpRequest'], typing.Optional['HttpResponse']
]
ResponseMiddelwareProcessorType = typing.Callable[
    ['ExtendedHttpRequest', 'HttpResponse'], 'HttpResponse'
]


def build_middleware(
    request_processor: RequestMiddelwareProcessorType,
    response_processor: ResponseMiddelwareProcessorType,
) -> typing.Callable[[typing.Any], typing.Union[typing.Callable, typing.Coroutine]]:
    """
    Creates a method to be used as a middleware, synchronously or asynchronously
    """

    @sync_and_async_middleware
    def middleware(
        get_response: typing.Any,
    ) -> typing.Union[typing.Callable, typing.Coroutine]:
        if asyncio.iscoroutinefunction(get_response):

            async def async_middleware(
                request: 'ExtendedHttpRequest',
            ) -> 'HttpResponse':
                response = request_processor(request)
                return response_processor(
                    request, response or await get_response(request)
                )

            return async_middleware
        else:

            def sync_middleware(request: 'ExtendedHttpRequest') -> 'HttpResponse':
                response = request_processor(request)
                return response_processor(request, response or get_response(request))

            return sync_middleware

    return middleware
