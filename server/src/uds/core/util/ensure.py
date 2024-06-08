# -*- coding: utf-8 -*-
#
# Copyright (c) 2013-2023 Virtual Cable S.L.U.
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
import typing
import collections.abc


def as_list(obj: typing.Any) -> list[typing.Any]:
    """
    Checks if the given object is a list or can be converted into a list.

    Args:
        obj (Any): The object to check.

    Returns:
        list[Any]: If the object is a list, it is returned as is.
                   If the object is a string or bytes, it is wrapped in a list and returned.
                   If the object is not iterable, a list containing the object is returned.

    """
    if obj is None:
        return []

    if isinstance(obj, (str, bytes, dict)):
        return [obj]

    if isinstance(obj, list):
        return typing.cast(list[typing.Any], obj)
    
    try:
        return list(obj)
    except Exception:  # Not iterable (list will fail)
        return [obj]


def as_iterable(obj: typing.Any) -> typing.Generator[typing.Any, None, None]:
    """Returns an iterable object from a single object or a list of objects

    Args:
        obj (typing.Union[T, collections.abc.Iterable[T]]): object to be converted to iterable

    Returns:
        typing.Generator[T, None, None]: Iterable object

    Yields:
        Iterator[typing.Generator[T, None, None]]: The object itself or the objects as iterated
    """
    if not obj:
        return

    if isinstance(obj, (str, bytes, dict)):
        yield obj
    else:
        if isinstance(obj, collections.abc.Iterable):
            yield from obj
            return
        yield obj  # if not iterable, return the object itself


T = typing.TypeVar('T')


def is_instance(obj: typing.Any, cls: type[T]) -> T:
    """Checks if an object is an instance of a class or a list of instances of a class

    Args:
        obj (typing.Union[T, collections.abc.Iterable[T]]): object to be checked
        cls (type[T]): Class to check

    Returns:
        T: The object if it's an instance of the class, casted to the class if it's a list of instances of the class

    Raises:
        ValueError: If the object is not an instance of the class
    """
    if not obj:
        return obj

    if isinstance(obj, cls):
        return obj

    raise ValueError(f'Object {obj} is not an instance of {cls}')
