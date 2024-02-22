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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import dataclasses
import functools
import inspect
import logging
import threading
import time
import typing
import collections.abc

from django.db import transaction

from uds.core import consts, types, exceptions
from uds.core.util import singleton

import uds.core.exceptions.rest

logger = logging.getLogger(__name__)

FT = typing.TypeVar('FT', bound=collections.abc.Callable[..., typing.Any])


# Caching statistics
class CacheStats(metaclass=singleton.Singleton):
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

    @staticmethod
    def manager() -> 'CacheStats':
        return CacheStats()


@dataclasses.dataclass
class CacheInfo:
    """
    Cache info
    """

    hits: int
    misses: int
    total: int
    exec_time: int


class ClassPropertyDescriptor:
    """
    Class property descriptor
    """

    def __init__(self, fget: collections.abc.Callable[..., typing.Any]) -> None:
        self.fget = fget

    def __get__(self, obj: typing.Any, cls: typing.Any = None) -> typing.Any:
        return self.fget(cls)


def classproperty(func: collections.abc.Callable[..., typing.Any]) -> ClassPropertyDescriptor:
    """
    Class property decorator
    """
    return ClassPropertyDescriptor(func)


def deprecated(func: FT) -> FT:
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @functools.wraps(func)
    def new_func(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
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

    return typing.cast(FT, new_func)


def deprecated_class_value(new_var_name: str) -> collections.abc.Callable[..., typing.Any]:
    """
    Decorator to make a class value deprecated and warn about it

    Example:
        @deprecatedClassValue('other.varname')
        def varname(self):  # It's like a property
            return self._varname  # Returns old value
    """

    class innerDeprecated:
        fget: collections.abc.Callable[..., typing.Any]
        new_var_name: str

        def __init__(self, method: collections.abc.Callable[..., typing.Any], newVarName: str) -> None:
            self.new_var_name = newVarName
            self.fget = method

        def __get__(self, instance: typing.Any, cls: typing.Any = None) -> typing.Any:
            try:
                caller = inspect.stack()[1]
                logger.warning(
                    'Use of deprecated class value %s from %s:%s. Use %s instead.',
                    self.fget.__name__,
                    caller.filename,
                    caller.lineno,
                    self.new_var_name,
                )
            except Exception:
                logger.info('No stack info on deprecated value use %s', self.fget.__name__)

            return self.fget(cls)

    return functools.partial(innerDeprecated, newVarName=new_var_name)


def ensure_connected(func: FT) -> FT:
    """This decorator calls "connect" method of the class of the wrapped object"""

    def new_func(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        args[0].connect()
        return func(*args, **kwargs)

    return typing.cast(FT, new_func)


# Decorator for caching
# This decorator will cache the result of the function for a given time, and given parameters
def cached(
    prefix: str,
    timeout: typing.Union[collections.abc.Callable[[], int], int] = -1,
    args: typing.Optional[typing.Union[collections.abc.Iterable[int], int]] = None,
    kwargs: typing.Optional[typing.Union[collections.abc.Iterable[str], str]] = None,
    key_helper: typing.Optional[collections.abc.Callable[[typing.Any], str]] = None,
) -> collections.abc.Callable[[FT], FT]:
    """Decorator that give us a "quick& clean" caching feature on db.
    The "cached" element must provide a "cache" variable, which is a cache object

    Parameters:
        prefix: Prefix to use for cache key
        timeout: Timeout for cache
        args: List of arguments to use for cache key (i.e. [0, 1] will use first and second argument for cache key, 0 will use "self" if a method, and 1 will use first argument)
        kwargs: List of keyword arguments to use for cache key (i.e. ['a', 'b'] will use "a" and "b" keyword arguments for cache key)
        key_fnc: Function to use for cache key. If provided, this function will be called with the same arguments as the wrapped function, and must return a string to use as cache key

    Note:
        If args and kwargs are not provided, all parameters (except *args and **kwargs) will be used for building cache key


    """
    from uds.core.util.cache import Cache  # To avoid circular references

    timeout = consts.cache.DEFAULT_CACHE_TIMEOUT if timeout == -1 else timeout
    args_list: list[int] = [args] if isinstance(args, int) else list(args or [])
    kwargs_list = [kwargs] if isinstance(kwargs, str) else list(kwargs or [])

    lock = threading.Lock()

    hits = misses = exec_time = 0

    def allow_cache_decorator(fnc: FT) -> FT:
        # If no caching args and no caching kwargs, we will cache the whole call
        # If no parameters provider, try to infer them from function signature
        try:
            if not args_list and not kwargs_list:
                for pos, (param_name, param) in enumerate(inspect.signature(fnc).parameters.items()):
                    if param_name == 'self':  # Self will provide a key, if necesary, using key_fnc
                        continue
                    # Parameters can be included twice in the cache, but it's not a problem
                    if param.kind in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.POSITIONAL_ONLY,
                    ):
                        args_list.append(pos)
                    if param.kind in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    ):
                        kwargs_list.append(param_name)
                    # *args and **kwargs are not supported as cache parameters
        except Exception:
            # Not inspectable, no caching possible, return original function
            return fnc

        lkey_fnc = key_helper or (lambda x: fnc.__name__)

        @functools.wraps(fnc)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            nonlocal hits, misses, exec_time
            with transaction.atomic():  # On its own transaction (for cache operations, that are on DB)
                cache_key: str = prefix
                for i in args_list:
                    if i < len(args):
                        cache_key += str(args[i])
                for s in kwargs_list:
                    cache_key += str(kwargs.get(s, ''))
                # Append key data
                cache_key += lkey_fnc(args[0] if len(args) > 0 else fnc.__name__)

                # Note tha this value (cache_key) will be hashed by cache, so it's not a problem if it's too long

                # Get cache from object if present, or use the global 'functionCache' (generic, common to all objects)
                inner_cache: 'Cache|None' = getattr(args[0], 'cache', None) if len(args) > 0 else None
                cache: 'Cache' = inner_cache or Cache('functionCache')

                # if timeout is a function, call it
                ltimeout = timeout() if callable(timeout) else timeout

                data: typing.Any = None
                # If misses is 0, we are starting, so we will not try to get from cache
                if not kwargs.get('force', False) and ltimeout > 0 and misses > 0:
                    data = cache.get(cache_key, default=consts.cache.CACHE_NOT_FOUND)
                    if data is not consts.cache.CACHE_NOT_FOUND:
                        with lock:
                            hits += 1
                            CacheStats.manager().add_hit(exec_time // hits)  # Use mean execution time
                        return data

                with lock:
                    misses += 1
                    CacheStats.manager().add_miss()

                if 'force' in kwargs:
                    # Remove force key
                    del kwargs['force']

                t = time.thread_time_ns()
                data = fnc(*args, **kwargs)
                exec_time += time.thread_time_ns() - t

                try:
                    # Maybe returned data is not serializable. In that case, cache will fail but no harm is done with this
                    cache.put(cache_key, data, ltimeout)
                except Exception as e:
                    logger.debug(
                        'Data for %s is not serializable on call to %s, not cached. %s (%s)',
                        cache_key,
                        fnc.__name__,
                        data,
                        e,
                    )
                return data

        def cache_info() -> CacheInfo:
            """Report cache statistics"""
            with lock:
                return CacheInfo(hits, misses, hits + misses, exec_time)

        def cache_clear() -> None:
            """Clear the cache and cache statistics"""
            nonlocal hits, misses, exec_time
            with lock:
                hits = misses = exec_time = 0

        # Same as lru_cache
        wrapper.cache_info = cache_info  # type: ignore
        wrapper.cache_clear = cache_clear  # type: ignore

        return typing.cast(FT, wrapper)

    return allow_cache_decorator


# Decorator to execute method in a thread
def threaded(func: FT) -> FT:
    """Decorator to execute method in a thread"""

    @functools.wraps(func)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()

    return typing.cast(FT, wrapper)


def blocker(
    request_attr: typing.Optional[str] = None,
    max_failures: typing.Optional[int] = None,
    ignore_block_config: bool = False,
) -> collections.abc.Callable[[FT], FT]:
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
    from uds.core.util.cache import Cache  # To avoid circular references
    from uds.core.util.config import GlobalConfig

    blockCache = Cache('uds:blocker')  # Cache for blocked ips

    max_failures = max_failures or consts.system.ALLOWED_FAILS

    def decorator(f: FT) -> FT:
        @functools.wraps(f)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            if not GlobalConfig.BLOCK_ACTOR_FAILURES.as_bool(True) and not ignore_block_config:
                return f(*args, **kwargs)

            request: typing.Optional['types.requests.ExtendedHttpRequest'] = getattr(
                args[0], request_attr or '_request', None
            )

            # No request object, so we can't block
            if request is None:
                return f(*args, **kwargs)

            ip = request.ip

            # if ip is blocked, raise exception
            failuresCount = blockCache.get(ip, 0)
            if failuresCount >= max_failures:
                raise exceptions.rest.AccessDenied

            try:
                result = f(*args, **kwargs)
            except uds.core.exceptions.rest.BlockAccess:
                # Increment
                blockCache.put(ip, failuresCount + 1, GlobalConfig.LOGIN_BLOCK.as_int())
                raise exceptions.rest.AccessDenied
            # Any other exception will be raised
            except Exception:
                raise

            # If we are here, it means that the call was successfull, so we reset the counter
            blockCache.delete(ip)

            return result

        return typing.cast(FT, wrapper)

    return decorator


def profile(
    log_file: typing.Optional[str] = None,
) -> collections.abc.Callable[[FT], FT]:
    """
    Decorator that will profile the wrapped function and log the results to the provided file

    Args:
        log_file: File to log the results. If None, it will log to "profile.log" file

    Returns:
        Decorator
    """

    def decorator(f: FT) -> FT:
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            nonlocal log_file
            import cProfile
            import pstats
            import tempfile

            log_file = log_file or tempfile.gettempdir() + f.__name__ + '.profile'

            profiler = cProfile.Profile()
            result = profiler.runcall(f, *args, **kwargs)
            stats = pstats.Stats(profiler)
            stats.strip_dirs()
            stats.sort_stats('cumulative')
            stats.dump_stats(log_file)
            return result

        return typing.cast(FT, wrapper)

    return decorator
