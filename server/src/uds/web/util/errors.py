# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import traceback
import json
import logging
import typing

from django.utils.translation import gettext_lazy as _
from django.shortcuts import render
from django.http import HttpResponse

from django.http import HttpResponseRedirect
from django.urls import reverse

from uds.core import types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import (
        HttpRequest,
    )  # pylint: disable=ungrouped-imports


logger = logging.getLogger(__name__)


def error_view(request: 'HttpRequest', errorCode: int) -> HttpResponseRedirect:
    return HttpResponseRedirect(reverse('page.error', kwargs={'err': errorCode}))


def error(request: 'HttpRequest', err: str) -> 'HttpResponse':
    """
    Error view, responsible of error display
    """
    return render(request, 'uds/modern/index.html', {})


def exception_view(request: 'HttpRequest', exception: Exception) -> HttpResponseRedirect:
    """
    Tries to render an error page with error information
    """
    logger.debug(traceback.format_exc())
    return error_view(request, types.errors.Error.from_exception(exception))


def error_message(request: 'HttpRequest', err: int) -> 'HttpResponse':
    """
    Error view, responsible of error display
    """
    return HttpResponse(
        json.dumps({'error': types.errors.Error.from_int(err).message, 'code': str(err)}),
        content_type='application/json',
    )
