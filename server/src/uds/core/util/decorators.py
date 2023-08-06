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
import functools
import logging
import inspect
import typing
import time
import threading
import hashlib

from uds.core.util.cache import Cache


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

    def add_miss(self) -> None:
        self.misses += 1
        self.total += 1

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


class CacheInfo(typing.NamedTuple):
    """
    Cache info
    """

    hits: int
    misses: int
    total: int
    exec_time: int


def deprecated(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @functools.wraps(func)
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


def deprecatedClassValue(newVarName: str) -> typing.Callable:
    """
    Decorator to make a class value deprecated and warn about it

    Example:
        @deprecatedClassValue('other.varname')
        def varname(self):  # It's like a property
            return self._varname  # Returns old value
    """
    class innerDeprecated:
        fget: typing.Callable
        new_var_name: str

        def __init__(self, method: typing.Callable, newVarName: str) -> None:
            self.new_var_name = newVarName
            self.fget = method  # type: ignore

        def __get__(self, instance, cls=None):
            try:
                caller = inspect.stack()[1]
                logger.warning(
                    'Use of deprecated class value %s from %s:%s. Use %s instead.',
                    self.fget.__name__,
                    caller[1],
                    caller[2],
                    self.new_var_name,
                )
            except Exception:
                logger.info(
                    'No stack info on deprecated value use %s', self.fget.__name__
                )

            return self.fget(cls)

    return functools.partial(innerDeprecated, newVarName=newVarName)


def ensureConnected(func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    """This decorator calls "connect" method of the class of the wrapped object"""

    @functools.wraps(func)
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
    cacheTimeout: typing.Union[typing.Callable[[], int], int] = -1,
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
    cacheTimeout = Cache.DEFAULT_VALIDITY if cacheTimeout == -1 else cacheTimeout
    cachingArgList: typing.List[int] = (
        [cachingArgs] if isinstance(cachingArgs, int) else list(cachingArgs or [])
    )
    cachingKwargList: typing.List[str] = (
        isinstance(cachingKWArgs, str) and [cachingKWArgs] or list(cachingKWArgs or [])
    )

    lock = threading.Lock()

    hits = misses = exec_time = 0

    def allowCacheDecorator(fnc: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
        # If no caching args and no caching kwargs, we will cache the whole call
        # If no parameters provider, try to infer them from function signature
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
                    elif param.kind in (
                        inspect.Parameter.KEYWORD_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    ):
                        cachingKwargList.append(paramName)
                    # *args and **kwargs are not supported
        except Exception:  # nosec
            pass  # Not inspectable, no caching

        keyFnc = cachingKeyFnc or (lambda x: fnc.__name__)

        @functools.wraps(fnc)
        def wrapper(*args, **kwargs) -> RT:
            nonlocal hits, misses, exec_time
            keyHash = hashlib.sha256(usedforsecurity=False)
            for i in cachingArgList:
                if i < len(args):
                    keyHash.update(str(args[i]).encode('utf-8'))
            for s in cachingKwargList:
                keyHash.update(str(kwargs.get(s, '')).encode('utf-8'))
            # Append key data
            keyHash.update(
                keyFnc(args[0] if len(args) > 0 else fnc.__name__).encode('utf-8')
            )
            # compute cache key
            cacheKey = f'{cachePrefix}-{keyHash.hexdigest()}'

            cache = getattr(args[0], 'cache', None) or Cache('functionCache')

            # if cacheTimeout is a function, call it
            timeout = cacheTimeout() if callable(cacheTimeout) else cacheTimeout

            data: typing.Any = None
            if not kwargs.get('force', False) and timeout > 0:
                data = cache.get(cacheKey)
                if data:
                    with lock:
                        hits += 1
                        stats.add_hit(exec_time // hits)  # Use mean execution time
                    return data

            with lock:
                misses += 1
                stats.add_miss()

            if 'force' in kwargs:
                # Remove force key
                del kwargs['force']

            t = time.thread_time_ns()
            data = fnc(*args, **kwargs)
            # Compute duration
            with lock:
                exec_time += time.thread_time_ns() - t

            try:
                # Maybe returned data is not serializable. In that case, cache will fail but no harm is done with this
                cache.put(cacheKey, data, timeout)
            except Exception as e:
                logger.debug(
                    'Data for %s is not serializable on call to %s, not cached. %s (%s)',
                    cacheKey,
                    fnc.__name__,
                    data,
                    e,
                )
            return data

        def cache_info() -> CacheInfo:
            """Report cache statistics"""
            with lock:
                return CacheInfo(hits, misses, hits+misses, exec_time)

        def cache_clear() -> None:
            """Clear the cache and cache statistics"""
            nonlocal hits, misses, exec_time
            with lock:
                hits = misses = exec_time = 0

        # Same as lru_cache
        wrapper.cache_info = cache_info  # type: ignore
        wrapper.cache_clear = cache_clear  # type: ignore

        return wrapper

    return allowCacheDecorator


# Decorator to execute method in a thread
def threaded(func: typing.Callable[..., None]) -> typing.Callable[..., None]:
    """Decorator to execute method in a thread"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()

    return wrapper
