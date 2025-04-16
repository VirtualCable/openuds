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

from uds.core import consts, types, exceptions

import uds.core.exceptions.rest

logger = logging.getLogger(__name__)

# FT = typing.TypeVar('FT', bound=collections.abc.Callable[..., typing.Any])
P = typing.ParamSpec('P')
R = typing.TypeVar('R')

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


def deprecated(func: collections.abc.Callable[P, R]) -> collections.abc.Callable[P, R]:
    """This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used."""

    @functools.wraps(func)
    def new_func(*args: P.args, **kwargs: P.kwargs) -> R:
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


def deprecated_class_value(new_var_name: str) -> collections.abc.Callable[..., typing.Any]:
    """
    Decorator to make a class value deprecated and warn about it

    Example:
        @deprecatedClassValue('other.varname')
        def varname(self):  # It's like a property
            return self._varname  # Returns old value
    """

    class InnerDeprecated:
        fget: collections.abc.Callable[..., typing.Any]
        new_var_name: str

        def __init__(self, method: collections.abc.Callable[..., typing.Any], new_var_name: str) -> None:
            self.new_var_name = new_var_name
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

    return functools.partial(InnerDeprecated, new_var_name=new_var_name)


# # So only classes that have a "connect" method can use this decorator
class _HasConnect(typing.Protocol):
    def connect(self) -> None: ...


# def ensure_connected(func: collections.abc.Callable[P, R]) -> collections.abc.Callable[P, R]:

# Keep this, but mypy does not likes it... it's perfect with pyright
# We use pyright for type checking, so we will use this
HasConnect = typing.TypeVar('HasConnect', bound=_HasConnect)


def ensure_connected(
    func: collections.abc.Callable[typing.Concatenate[HasConnect, P], R]
) -> collections.abc.Callable[typing.Concatenate[HasConnect, P], R]:
    """This decorator calls "connect" method of the class of the wrapped object"""

    @functools.wraps(func)
    def new_func(obj: HasConnect, /, *args: P.args, **kwargs: P.kwargs) -> R:
        # self = typing.cast(_HasConnect, args[0])
        obj.connect()
        return func(obj, *args, **kwargs)

    return new_func

# To be used in a future, for type checking only
# currently the problem is that the signature of a function is diferent
# thant the signature of a class method, so we can't use the same decorator
# Also, if we change the return type, abstract methods will not be able to be implemented
# because derieved will not have the same signature
# Also, R must be covariant for proper type checking
# class CacheMethods(typing.Protocol[P, R]):
#     def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...
#     def cache_clear(self) -> None: ...
#     def cache_info(self) -> CacheInfo: ...
# Now, we could use this by creating two decorators, one for the class methods and one for the functions
# But the inheritance problem will still be there, so we will keep the current implementation

# Decorator for caching
# This decorator will cache the result of the function for a given time, and given parameters
def cached(
    prefix: typing.Optional[str] = None,
    timeout: typing.Union[collections.abc.Callable[[], int], int] = -1,
    args: typing.Optional[typing.Union[collections.abc.Iterable[int], int]] = None,
    kwargs: typing.Optional[typing.Union[collections.abc.Iterable[str], str]] = None,
    key_helper: typing.Optional[collections.abc.Callable[[typing.Any], str]] = None,
) -> collections.abc.Callable[[collections.abc.Callable[P, R]], collections.abc.Callable[P, R]]:
    """
    Decorator that gives us a "quick & clean" caching feature on the database.

    Parameters:
        prefix (str): Prefix to use for the cache key.
        timeout (Union[Callable[[], int], int], optional): Timeout for the cache in seconds. If -1, it will use the default timeout. Defaults to -1.
        args (Optional[Union[Iterable[int], int]], optional): List of arguments to use for the cache key. If an integer is provided, it will be treated as a single argument. Defaults to None.
        kwargs (Optional[Union[Iterable[str], str]], optional): List of keyword arguments to use for the cache key. If a string is provided, it will be treated as a single keyword argument. Defaults to None.
        key_helper (Optional[Callable[[Any], str]], optional): Function to use for improving the calculated cache key. Defaults to None.

    Note:
        If `args` and `kwargs` are not provided, all parameters (except `*args` and `**kwargs`) will be used for building the cache key.

    Note:
        * The `key_helper` function will receive the first argument of the function (`self`) and must return a string that will be appended to the cache key.
        * Also the cached decorator, if no args provided, must be the last decorator unless all underlying decorators uses functools.wraps
          This is because the decorator will try to infer the parameters from the function signature,
          and if the function signature is not available, it will cache the result no matter the parameters.
    """
    from uds.core.util.cache import Cache  # To avoid circular references

    timeout = consts.cache.DEFAULT_CACHE_TIMEOUT if timeout == -1 else timeout
    args_list: list[int] = [args] if isinstance(args, int) else list(args or [])
    kwargs_list = [kwargs] if isinstance(kwargs, str) else list(kwargs or [])

    hits = misses = exec_time = 0

    # Add a couple of methods to the wrapper to allow cache statistics access and cache clearing
    def cache_info() -> CacheInfo:
        """Report cache statistics"""
        return CacheInfo(hits, misses, hits + misses, exec_time)

    def cache_clear() -> None:
        """Clear the cache and cache statistics"""
        nonlocal hits, misses, exec_time
        hits = misses = exec_time = 0

    def allow_cache_decorator(fnc: collections.abc.Callable[P, R]) -> collections.abc.Callable[P, R]:
        # If no caching args and no caching kwargs, we will cache the whole call
        # If no parameters provided, try to infer them from function signature
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
            logger.debug('Function %s is not inspectable, no caching possible', fnc.__name__)
            # Not inspectable, no caching possible, return original function
            
            # Ensure compat with methods of cached functions
            setattr(fnc, 'cache_info', cache_info)
            setattr(fnc, 'cache_clear', cache_clear)
            return fnc

        key_helper_fnc: collections.abc.Callable[[typing.Any], str] = key_helper or (lambda x: fnc.__name__)

        @functools.wraps(fnc)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal hits, misses, exec_time

            cache_key: str = prefix or fnc.__name__
            for i in args_list:
                if i < len(args):
                    cache_key += str(args[i])
            for s in kwargs_list:
                cache_key += str(kwargs.get(s, ''))

            # Append key helper to cache key and get real cache
            # Note tha this value (cache_key) will be hashed by cache, so it's not a problem if it's too long
            if len(args) > 0:
                cache_key += key_helper_fnc(args[0])
                inner_cache: 'Cache|None' = getattr(args[0], 'cache', None)
            else:
                cache_key += key_helper_fnc(fnc.__name__)
                inner_cache = None

            # Get cache from object if present,
            # or if args[0] is an object, use its class name as cache name
            # or use the global 'functionCache' (generic, common cache, may clash with other functions)
            cache = inner_cache or Cache(
                (getattr(getattr(args[0], '__class__', None), '__name__', None) if len(args) > 0 else None)
                or 'functionCache'
            )

            # if timeout is a function, call it
            effective_timeout = timeout() if callable(timeout) else timeout

            data: typing.Any = None
            # If misses is 0, we are starting, so we will not try to get from cache
            if not kwargs.get('force', False) and effective_timeout > 0 and misses > 0:
                data = cache.get(cache_key, default=consts.cache.CACHE_NOT_FOUND)
                if data is not consts.cache.CACHE_NOT_FOUND:
                    hits += 1
                    return data

            misses += 1

            if 'force' in kwargs:
                # Remove force key
                del kwargs['force']

            # Execute the function outside the DB transaction
            t = time.thread_time_ns()
            data = fnc(*args, **kwargs)  # pyright: ignore  # For some reason, pyright does not like this line
            exec_time += time.thread_time_ns() - t

            try:
                # Maybe returned data is not serializable. In that case, cache will fail but no harm is done with this
                cache.put(cache_key, data, effective_timeout)
            except Exception as e:
                logger.debug(
                    'Data for %s is not serializable on call to %s, not cached. %s (%s)',
                    cache_key,
                    fnc.__name__,
                    data,
                    e,
                )
            return data

        # Same as lru_cache
        setattr(wrapper, 'cache_info', cache_info)
        setattr(wrapper, 'cache_clear', cache_clear)

        return wrapper

    return allow_cache_decorator


# Decorator to execute method in a thread
def threaded(func: collections.abc.Callable[P, None]) -> collections.abc.Callable[P, None]:
    """Decorator to execute method in a thread"""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> None:
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.start()

    return wrapper


def blocker(
    request_attr: typing.Optional[str] = None,
    max_failures: typing.Optional[int] = None,
    ignore_block_config: bool = False,
) -> collections.abc.Callable[[collections.abc.Callable[P, R]], collections.abc.Callable[P, R]]:
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

    mycache = Cache('uds:blocker')  # Cache for blocked ips

    max_failures = max_failures or consts.system.ALLOWED_FAILS

    def decorator(f: collections.abc.Callable[P, R]) -> collections.abc.Callable[P, R]:
        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not GlobalConfig.BLOCK_ACTOR_FAILURES.as_bool(True) and not ignore_block_config:
                try:
                    return f(*args, **kwargs)
                except uds.core.exceptions.rest.BlockAccess:
                    raise exceptions.rest.AccessDenied

            request: typing.Optional[typing.Any] = getattr(args[0], request_attr or '_request', None)

            # No request object, so we can't block
            if request is None or not isinstance(request, types.requests.ExtendedHttpRequest):
                logger.debug('No request object, so we can\'t block: (value is %s)', request)
                return f(*args, **kwargs)

            ip = request.ip

            # if ip is blocked, raise exception
            failures_count: int = mycache.get(ip, 0)
            if failures_count >= max_failures:
                raise exceptions.rest.AccessDenied

            try:
                result = f(*args, **kwargs)
            except uds.core.exceptions.rest.BlockAccess:
                # Increment
                mycache.put(ip, failures_count + 1, GlobalConfig.LOGIN_BLOCK.as_int())
                raise exceptions.rest.AccessDenied
            # Any other exception will be raised
            except Exception:
                raise

            # If we are here, it means that the call was successfull, so we reset the counter
            mycache.delete(ip)

            return result

        return wrapper

    return decorator


def profiler(
    log_file: typing.Optional[str] = None,
) -> collections.abc.Callable[[collections.abc.Callable[P, R]], collections.abc.Callable[P, R]]:
    """
    Decorator that will profile the wrapped function and log the results to the provided file

    Args:
        log_file: File to log the results. If None, it will log to "profile.log" file

    Returns:
        Decorator
    """

    def decorator(f: collections.abc.Callable[P, R]) -> collections.abc.Callable[P, R]:

        @functools.wraps(f)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            nonlocal log_file  # use outer log_file
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

        return wrapper

    return decorator
