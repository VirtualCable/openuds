# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import datetime
import logging
import typing
import collections.abc

from django.utils.translation import get_language
from django.utils import formats

from uds.core import consts

if typing.TYPE_CHECKING:
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports

logger = logging.getLogger(__name__)


def uds_link(request: 'HttpRequest', ticket: str, scrambler: str) -> str:
    # Removed http support, so only udss:// links are generated

    # If we have a scheme, remove it
    rels = request.build_absolute_uri("/").split("://", maxsplit=1)
    rel = rels[1] if len(rels) > 1 else rels[0]

    # Ensure that build_absolute_uri returns a valid url without scheme
    return f'udss://{rel}{ticket}/{scrambler}'


def uds_access_link(
    request: 'HttpRequest',  # pylint: disable=unused-argument
    serviceId: str,
    transportId: typing.Optional[str],
) -> str:
    '''
    If transportId (uuid) is None, this will be a metaLink
    '''
    return f'{consts.system.UDS_ACTION_SCHEME}{serviceId}/{transportId or "meta"}'


def parse_date(dateToParse) -> datetime.date:
    if get_language() == 'fr':
        date_format = '%d/%m/%Y'
    else:
        date_format = (
            formats.get_format('SHORT_DATE_FORMAT').replace('Y', '%Y').replace('m', '%m').replace('d', '%d')
        )  # pylint: disable=maybe-no-member

    return datetime.datetime.strptime(dateToParse, date_format).date()


def date_to_literal(date) -> str:
    # Fix for FR lang for datepicker
    if get_language() == 'fr':
        date = date.strftime('%d/%m/%Y')
    else:
        date = formats.date_format(date, 'SHORT_DATE_FORMAT')

    return date


def extract_key(
    dictionary: dict, key: typing.Any, fmt: typing.Optional[str] = None, default: typing.Any = None
):
    fmt = fmt or '{0}'
    default = default or ''

    if key in dictionary:
        value = fmt.format(dictionary[key])
        del dictionary[key]
    else:
        value = default
    return value
