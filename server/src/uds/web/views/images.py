# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from django.http import HttpResponse
from django.views.decorators.cache import cache_page

from uds.core.consts.images import DEFAULT_IMAGE
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.util.model import process_uuid
from uds.models import Image, Transport

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import HttpRequest  # pylint: disable=ungrouped-imports


@cache_page(3600, key_prefix='img', cache='memory')
def image(request: 'HttpRequest', image_id: str) -> 'HttpResponse':
    try:
        icon = Image.objects.get(uuid=process_uuid(image_id))
        return icon.image_as_response()
    except Image.DoesNotExist:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')


@cache_page(3600, key_prefix='img', cache='memory')
def transport_icon(request: 'ExtendedHttpRequest', transport_id: str) -> HttpResponse:
    try:
        transport: Transport
        if transport_id[:6] == 'LABEL:':
            # Get First label
            transport = Transport.objects.filter(label=transport_id[6:]).order_by('priority')[0]
        else:
            transport = Transport.objects.get(uuid=process_uuid(transport_id))
        return HttpResponse(transport.get_instance().icon(), content_type='image/png')
    except Exception:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')


@cache_page(3600, key_prefix='img', cache='memory')
def service_image(request: 'ExtendedHttpRequest', idImage: str) -> HttpResponse:
    try:
        icon = Image.objects.get(uuid=process_uuid(idImage))
        return icon.image_as_response()
    except Image.DoesNotExist:
        pass  # Tries to get image from transport

    try:
        transport: Transport = Transport.objects.get(uuid=process_uuid(idImage))
        return HttpResponse(transport.get_instance().icon(), content_type='image/png')
    except Exception:
        return HttpResponse(DEFAULT_IMAGE, content_type='image/png')
