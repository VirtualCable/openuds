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
import typing
import collections.abc
import logging

logger = logging.getLogger(__name__)

T = typing.TypeVar('T', bound=typing.Any)


# We want to write something like this:
# (('<arg>', '<arg2>', 'literal', '<other_arg>', '<other_arg2>', 'literal2', ...), callback)
# Where callback is a function that will be called with the arguments in the order they are
# in the tuple, and the literals will be ignored
# So, for example, if we have a tuple like this:
# ('<sample>', '<arg_2>', 'literal', 'other_literal', '<argument>', 'literal2')
# The callback will be called with the arguments in the order they are in the tuple, so:
# callback(sample, arg_2, argument)
# And the literals will be ignored
def match_args(
    arg_list: collections.abc.Iterable[str],
    error: collections.abc.Callable[..., typing.Any],
    *args: tuple[tuple[str, ...], collections.abc.Callable[..., T]],
) -> typing.Any:
    """
    Matches a list of arguments against a list of matchers.

    The matchers are a list of tuples, where the first element is a tuple of strings
    that will be used to match the arguments, and the second element is a function
    that will be called with the arguments in the order they are in the tuple, and the
    literals will be ignored

    So, for example, if we have a tuple like this:
    ('<sample>', '<arg_2>', 'literal', 'other_literal', '<argument>', 'literal2')
    The callback will be called with the arguments in the order they are in the tuple, so:
    callback(sample, arg_2, argument)
    And the literals will be ignored
    """
    arg_list = [i for i in arg_list]  # ensure it is a list
    for pattern, function in args:
        if len(arg_list) != len(pattern):
            continue

        # Check if all the arguments match
        matched = True
        for i, arg in enumerate(arg_list):
            if pattern[i].startswith('<') and pattern[i].endswith('>'):
                continue

            if arg != pattern[i]:
                matched = False
                break

        if matched:
            # All the arguments match, call the callback
            return function(
                *[
                    arg
                    for i, arg in enumerate(arg_list)
                    if pattern[i].startswith('<') and pattern[i].endswith('>')
                ]
            )

    logger.warning('No match found for %s with %s', arg_list, args)
    # Invoke error callback
    error()
    return None  # In fact, error is expected to raise an exception, so this is never reached

