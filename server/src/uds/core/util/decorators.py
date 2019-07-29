# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
from functools import wraps
import typing
import logging
import inspect

from uds.core.util.html import checkBrowser
from uds.web.util import errors


logger = logging.getLogger(__name__)


# Decorator that protects pages that needs at least a browser version
# Default is to deny IE < 9
def denyBrowsers(
        browsers: typing.Optional[typing.List[str]] = None,
        errorResponse: typing.Callable = lambda request: errors.errorView(request, errors.BROWSER_NOT_SUPPORTED)
    ):
    """
    Decorator to set protection to access page
    Look for samples at uds.core.web.views
    """

    if browsers is None:
        browsers = ['ie<9']

    def wrap(view_func):

        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            """
            Wrapped function for decorator
            """
            for b in browsers:
                if checkBrowser(request, b):
                    return errorResponse(request)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return wrap


def deprecated(func):
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @wraps(func)
    def new_func(*args, **kwargs):
        try:
            caller = inspect.stack()[1]
            logger.warning('Call to deprecated function %s from %s:%s.', func.__name__, caller[1], caller[2])
        except Exception:
            logger.info('No stack info on deprecated function call %s', func.__name__)

        return func(*args, **kwargs)

    return new_func


# Decorator that allows us a "fast&clean" caching system on service providers
#
# Decorator for caching
# Decorator that tries to get from cache before executing
def allowCache(
        cachePrefix: str,
        cacheTimeout: int,
        cachingArgs: typing.Optional[typing.Union[typing.List[int], int]] = None,
        cachingKeyFnc: typing.Optional[typing.Callable] = None
    ):
    """Decorator that give us a "quick& clean" caching feature on service providers.

    Note: This decorator is intended ONLY for service providers

    :param cachePrefix: the cache key "prefix" (prepended on generated key from args)
    :param cacheTimeout: The cache timeout in seconds
    :param cachingArgs: The caching args. Can be a single integer or a list.
                        First arg (self) is 0, so normally cachingArgs are 1, or [1,2,..]
    """
    if not cachingKeyFnc:
        cachingKeyFnc = lambda x: ''

    def allowCacheDecorator(fnc: typing.Callable):
        @wraps(fnc)
        def wrapper(*args, **kwargs):
            if cachingArgs is not None:
                if isinstance(cachingArgs, (list, tuple)):
                    argList = [args[i] if i < len(args) else '' for i in cachingArgs]
                else:
                    argList = args[cachingArgs] if cachingArgs < len(args) else ''
                cacheKey = '{}-{}.{}'.format(cachePrefix, cachingKeyFnc(args[0]), argList)
            else:
                cacheKey = '{}-{}.gen'.format(cachePrefix, cachingKeyFnc(args[0]))

            data = None
            if kwargs.get('force', False) is False and args[0].cache is not None:
                data = args[0].cache.get(cacheKey)

            if kwargs.has_key('force'):
                # Remove force key
                del kwargs['force']

            if data is None:
                data = fnc(*args, **kwargs)
                try:
                    # Maybe returned data is not serializable. In that case, cache will fail but no harm is done with this
                    args[0].cache.put(cacheKey, data, cacheTimeout)
                except Exception as e:
                    logger.debug('Data for %s is not serializable on call to %s, not cached. %s (%s)', cacheKey, fnc.__name__, data, e)
            return data

        return wrapper

    return allowCacheDecorator

