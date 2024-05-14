# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import collections.abc
import typing
import functools
import dataclasses
from unittest import mock

@dataclasses.dataclass
class AutoSpecMethodInfo:
    name: str|typing.Callable[..., typing.Any]
    returns: typing.Any = None  # Can be a callable or a value
    partial_args: typing.Tuple[typing.Any, ...] = ()
    partial_kwargs: dict[str, typing.Any] = dataclasses.field(default_factory=dict)
    
    
def autospec(cls: type, metods_info: collections.abc.Iterable[AutoSpecMethodInfo], **kwargs: typing.Any) -> mock.Mock:
    """
    This is a helper function that will create a mock object with the same methods as the class passed as parameter.
    This is useful for testing purposes, where you want to mock a class and still have the same methods available.
    
    Take some care when using decorators and methods instead of string for its name. Ensure decorator do not hide the original method.
    (using functools.wraps or similar will do the trick, but take care of it)
    
    The returned value is in fact a mock object, but with the same methods as the class passed as parameter.
    """
    obj = mock.create_autospec(cls, **kwargs)
    for method_info in metods_info:
        # Set the return value for the method or the side_effect
        name = method_info.name if isinstance(method_info.name, str) else method_info.name.__name__
        mck = getattr(obj, name)
        if callable(method_info.returns):
            mck.side_effect = functools.partial(method_info.returns, *method_info.partial_args, **method_info.partial_kwargs)
            #mck.side_effect = method_info.returns
        else:
            mck.return_value = method_info.returns
            
    return obj