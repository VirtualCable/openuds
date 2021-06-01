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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import threading
import datetime
import weakref
import logging
import typing

from django.http import HttpRequest

from uds.core.util.tools import DictAsObj
from uds.models import User

logger = logging.getLogger(__name__)

_requests: typing.Dict[int, typing.Tuple[weakref.ref, datetime.datetime]] = {}


class ExtendedHttpRequest(HttpRequest):
    ip: str
    ip_proxy: str
    os: DictAsObj
    user: typing.Optional[User]  # type: ignore   # HttpRequests users "user" for it own, but we redefine it because base is not used...


class ExtendedHttpRequestWithUser(ExtendedHttpRequest):
    user: User


def getIdent() -> int:
    ident = threading.current_thread().ident
    return ident if ident else -1


def getRequest() -> ExtendedHttpRequest:
    ident = getIdent()
    if ident in _requests:
        val = typing.cast(
            typing.Optional[ExtendedHttpRequest], _requests[ident][0]()
        )  # Return obj from weakref
        if val:
            return val

    return ExtendedHttpRequest()

def delCurrentRequest() -> None:
    ident = getIdent()
    logger.debug('Deleting %s', ident)
    try:
        if ident in _requests:
            del _requests[ident]  # Remove stored request
        else:
            logger.info('Request id %s not stored in cache', ident)
    except Exception:
        logger.exception('Deleting stored request')

def cleanOldRequests() -> None:
    logger.debug('Cleaning stuck requests from %s', _requests)
    # No request lives 60 seconds, so 60 seconds is fine
    cleanFrom: datetime.datetime = datetime.datetime.now() - datetime.timedelta(
        seconds=60
    )
    toDelete: typing.List[int] = []
    for ident, request in _requests.items():
        if request[1] < cleanFrom:
            toDelete.append(ident)
    for ident in toDelete:
        try:
            del _requests[ident]
        except Exception:
            pass  # Ignore it silently
    

def setRequest(request: ExtendedHttpRequest):
    _requests[getIdent()] = (
        weakref.ref(typing.cast(ExtendedHttpRequest, request)),
        datetime.datetime.now(),
    )
