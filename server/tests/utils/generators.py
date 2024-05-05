# -*- coding: utf-8 -*-
#
# Copyright (c) 2022-2024 Virtual Cable S.L.U.
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

import random
import uuid
import typing

from . import constants

def random_string(size: int = 6, chars: typing.Optional[str] = None) -> str:
    chars = chars or constants.STRING_CHARS
    return ''.join(
        random.choice(chars) for _ in range(size)  # nosec: Not used for cryptography, just for testing
    )


def random_utf8_string(size: int = 6) -> str:
    # Generate a random utf-8 string of length "length"
    # some utf-8 non ascii chars are generated, but not all of them
    return ''.join(random.choice(constants.UTF_CHARS) for _ in range(size))  # nosec


def random_uuid() -> str:
    return str(uuid.uuid4())


def random_int(start: int = 0, end: int = 100000) -> int:
    return random.randint(start, end)  # nosec


def random_ip() -> str:
    return '.'.join(
        str(random.randint(0, 255)) for _ in range(4)  # nosec: Not used for cryptography, just for testing
    )


def random_mac() -> str:
    return ':'.join(random_string(2, '0123456789ABCDEF') for _ in range(6))


def limited_iterator(until_checker: typing.Callable[[], bool], limit: int = 128) -> typing.Generator[int, None, None]:
    """
    Limit an iterator to a number of elements
    Will continue until limit is reached or check() returns False
    """
    current = 0
    while current < limit and until_checker():
        yield current
        current += 1

    if current < limit:
        return

    # Limit reached, raise an exception
    raise Exception(f'Limit reached: {current}/{limit}: {until_checker()}')
