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
'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import json
import typing
import re
import collections.abc

from uds.core.consts.system import VERSION
from uds.core.util.model import sql_stamp_seconds


def rest_result(result: typing.Any, **kwargs: typing.Any) -> dict[str, typing.Any]:
    '''
    Returns a REST result
    '''
    # A common possible value in kwargs is "error"
    return {'result': result, 'stamp': sql_stamp_seconds(), 'version': VERSION, **kwargs}


def camel_and_snake_case_from(text: str) -> tuple[str, str]:
    '''
    Returns a tuple with the camel case and snake case of a text
    first value is camel case, second is snake case
    '''
    snake_case_name = re.sub(r'(?<!^)(?=[A-Z])', '_', text).lower()
    # And snake case to camel case (first letter lower case, rest upper case)
    camel_case_name = ''.join(x.capitalize() for x in snake_case_name.split('_'))
    camel_case_name = camel_case_name[0].lower() + camel_case_name[1:]

    return camel_case_name, snake_case_name


def to_incremental_json(
    source: collections.abc.Generator[typing.Any, None, None]
) -> typing.Generator[str, None, None]:
    '''
    Converts a generator to a json incremental string
    '''
    yield '['
    first = True
    for item in source:
        if first:
            first = False
        else:
            yield ','
        yield json.dumps(item)
    yield ']'
