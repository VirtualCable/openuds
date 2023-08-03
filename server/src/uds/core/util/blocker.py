# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import functools
import logging
import typing

from uds.core import consts
from uds.core.exceptions import BlockAccess
from uds.core.util.cache import Cache
from uds.core.util.config import GlobalConfig
from uds.REST.exceptions import AccessDenied

if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)

blockCache = Cache('uds:blocker')  # One year

RT = typing.TypeVar('RT')


def blocker(
    request_attr: typing.Optional[str] = None,
) -> typing.Callable[[typing.Callable[..., RT]], typing.Callable[..., RT]]:
    """
    Decorator that will block the actor if it has more than ALLOWED_FAILS failures in BLOCK_ACTOR_TIME seconds
    GlobalConfig.BLOCK_ACTOR_FAILURES.getBool() --> If true, block actor after ALLOWED_FAILS failures
    for LOGIN_BLOCK.getInt() seconds

    This decorator is intended only for Classes that, somehow, can provide the "request" object, and only
    for class methods, that is that have "self" as first parameter

    Args:
        request_attr: Name of the attribute that contains the request object. If None, it will try to get it from "_request" attribute

    Returns:
        Decorator

    """

    def decorator(f: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
        @functools.wraps(f)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> RT:
            if not GlobalConfig.BLOCK_ACTOR_FAILURES.getBool(True):
                return f(*args, **kwargs)

            request: typing.Optional['ExtendedHttpRequest'] = getattr(args[0], request_attr or '_request', None)

            # No request object, so we can't block
            if request is None:
                return f(*args, **kwargs)

            ip = request.ip

            # if ip is blocked, raise exception
            failuresCount = blockCache.get(ip, 0)
            if failuresCount >= consts.ALLOWED_FAILS:
                raise AccessDenied

            try:
                result = f(*args, **kwargs)
            except BlockAccess:
                # Increment
                blockCache.put(ip, failuresCount + 1, GlobalConfig.LOGIN_BLOCK.getInt())
                raise AccessDenied
            # Any other exception will be raised
            except Exception:
                raise

            # If we are here, it means that the call was successfull, so we reset the counter
            blockCache.delete(ip)

            return result

        return wrapper

    return decorator
