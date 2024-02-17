# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
from functools import wraps
import logging
import inspect
import typing
import time
import threading

from uds.core.util.html import checkBrowser
from uds.core.util.cache import Cache
from uds.web.util import errors


logger = logging.getLogger(__name__)

RT = typing.TypeVar('RT')

# Caching statistics
class StatsType:
    __slots__ = ('hits', 'misses', 'total', 'start_time', 'saving_time')

    hits: int
    misses: int
    total: int
    start_time: float
    saving_time: int  # in nano seconds
    
    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.total = 0
        self.start_time = time.time()
        self.saving_time = 0

    def add_hit(self, saving_time: int = 0) -> None:
        self.hits += 1
        self.total += 1
        self.saving_time += saving_time

    def add_miss(self, saving_time: int = 0) -> None:
        self.misses += 1
        self.total += 1
        self.saving_time += saving_time

    @property
    def uptime(self) -> float:
        return time.time() - self.start_time

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        return self.misses / self.total if self.total > 0 else 0.0

    def __str__(self) -> str:
        return (
            f'CacheStats: {self.hits}/{self.misses} on {self.total}, '
            f'uptime={self.uptime}, hit_rate={self.hit_rate:.2f}, '
            f'saving_time={self.saving_time/1000000:.2f}'
        )

stats = StatsType()

# Decorator that protects pages that needs at least a browser version
# Default is to deny IE < 9
def denyBrowsers(
    browsers: typing.Optional[typing.List[str]] = None,
    errorResponse: typing.Callable = lambda request: errors.errorView(
        request, errors.BROWSER_NOT_SUPPORTED
    ),
) -> typing.Callable[[typing.Callable[..., RT]], typing.Callable[..., RT]]:
    """
    Decorator to set protection to access page
    Look for samples at uds.core.web.views
    """

    denied: typing.List[str] = browsers or ['ie<9']

    def wrap(view_func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs) -> RT:
            """
            Wrapped function for decorator
            """
            for b in denied:
                if checkBrowser(request, b):
                    return errorResponse(request)

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return wrap


def deprecated(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @wraps(func)
    def new_func(*args, **kwargs) -> RT:
        try:
            caller = inspect.stack()[1]
            logger.warning(
                'Call to deprecated function %s from %s:%s.',
                func.__name__,
                caller[1],
                caller[2],
            )
        except Exception:
            logger.info('No stack info on deprecated function call %s', func.__name__)

        return func(*args, **kwargs)

    return new_func


def ensureConnected(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    """This decorator calls "connect" method of the class of the wrapped object"""

    @wraps(func)
    def new_func(*args, **kwargs) -> RT:
        args[0].connect()
        return func(*args, **kwargs)

    return new_func


# Decorator that allows us a "fast&clean" caching system on service providers
#
# Decorator for caching
# Decorator that tries to get from cache before executing
def allowCache(
    cachePrefix: str,
    cacheTimeout: int,
    cachingArgs: typing.Optional[typing.Union[typing.Iterable[int], int]] = None,
    cachingKWArgs: typing.Optional[typing.Union[typing.Iterable[str], str]] = None,
    cachingKeyFnc: typing.Optional[typing.Callable[[typing.Any], str]] = None,
) -> typing.Callable[[typing.Callable[..., RT]], typing.Callable[..., RT]]:
    """Decorator that give us a "quick& clean" caching feature.
    The "cached" element must provide a "cache" variable, which is a cache object

    Parameters:
        cachePrefix: Prefix to use for cache key
        cacheTimeout: Timeout for cache
        cachingArgs: List of arguments to use for cache key (i.e. [0, 1] will use first and second argument for cache key, 0 will use "self" if a method, and 1 will use first argument)
        cachingKWArgs: List of keyword arguments to use for cache key (i.e. ['a', 'b'] will use "a" and "b" keyword arguments for cache key)
        cachingKeyFnc: Function to use for cache key. If provided, this function will be called with the same arguments as the wrapped function, and must return a string to use as cache key
    
    Note: 
        If cachingArgs and cachingKWArgs are not provided, the whole arguments will be used for cache key

    """

    cachingArgList: typing.List[int] = (
        [cachingArgs] if isinstance(cachingArgs, int) else list(cachingArgs or [])
    )
    cachingKwargList: typing.List[str] = (
        isinstance(cachingKWArgs, str) and [cachingKWArgs] or list(cachingKWArgs or [])
    )

    def allowCacheDecorator(fnc: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
        # If no caching args and no caching kwargs, we will cache the whole call
        # If no parameters provider, try to infer them from function signature
        setattr(fnc, '__cache_hit__', 0)  # Cache hit
        setattr(fnc, '__cache_miss__', 0) # Cache miss
        setattr(fnc, '__exec_time__', 0)  # Execution time
        try:
            if cachingArgList is None and cachingKwargList is None:
                for pos, (paramName, param) in enumerate(
                    inspect.signature(fnc).parameters.items()
                ):
                    if paramName == 'self':
                        continue
                    # Parameters can be included twice in the cache, but it's not a problem
                    if param.kind in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.POSITIONAL_ONLY,
                    ):
                        cachingArgList.append(pos)
                    elif param.kind in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                        cachingKwargList.append(paramName)
                    # *args and **kwargs are not supported                    
        except Exception:
            pass  # Not inspectable, no caching
        
        keyFnc = cachingKeyFnc or (lambda x: fnc.__name__)
        
        @wraps(fnc)
        def wrapper(*args, **kwargs) -> RT:
            argList: str = '.'.join(
                [str(args[i]) for i in cachingArgList if i < len(args)]
                + [str(kwargs.get(i, '')) for i in cachingKwargList]
            )
            # If invoked from a class, and the class provides "cache"
            # we will use it, otherwise, we will use a global cache
            cache: 'Cache' = getattr(args[0], 'cache', None) or Cache('functionCache')
            kkey = keyFnc(args[0]) if len(args) > 0 else ''
            cacheKey = '{}-{}.{}'.format(cachePrefix, kkey, argList)

            data: typing.Any = None
            if not kwargs.get('force', False) and cacheTimeout > 0:
                NOT_FOUND = object()
                data = cache.get(cacheKey, defValue=NOT_FOUND)
                if data is not NOT_FOUND:
                    setattr(fnc, '__cache_hit__', getattr(fnc, '__cache_hit__') + 1)
                    stats.add_hit(getattr(fnc, '__exec_time__'))
                    return data

            setattr(fnc, '__cache_miss__', getattr(fnc, '__cache_miss__') + 1)
            stats.add_miss(getattr(fnc, '__exec_time__'))

            if 'force' in kwargs:
                # Remove force key
                del kwargs['force']

            t = time.thread_time_ns()
            data = fnc(*args, **kwargs)
            setattr(fnc, '__exec_time__', getattr(fnc, '__exec_time__') + time.thread_time_ns() - t)
            try:
                # Maybe returned data is not serializable. In that case, cache will fail but no harm is done with this
                cache.put(cacheKey, data, cacheTimeout)
            except Exception as e:
                logger.debug(
                    'Data for %s is not serializable on call to %s, not cached. %s (%s)',
                    cacheKey,
                    fnc.__name__,
                    data,
                    e,
                )
            return data

        return wrapper

    return allowCacheDecorator


# Decorator to execute method in a thread
def threaded(func: typing.Callable[..., None]) -> typing.Callable[..., None]:
    """Decorator to execute method in a thread"""

    @wraps(func)
    def wrapper(*args, **kwargs) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()

    return wrapper
