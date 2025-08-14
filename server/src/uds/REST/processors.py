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
import collections.abc
import datetime
import json
import logging
import time
import typing

from django.http import HttpResponse
from django.utils.functional import Promise as DjangoPromise

from uds.core import consts, types

from .utils import to_incremental_json

# from xml_marshaller import xml_marshaller

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.http import HttpRequest


class ParametersException(Exception):
    pass


class ContentProcessor:
    """
    Process contents (request/response) so Handlers can manage them
    """

    mime_type: typing.ClassVar[str] = ''
    extensions: typing.ClassVar[collections.abc.Iterable[str]] = []

    _request: 'HttpRequest'
    _odata: 'types.rest.api.ODataParams|None' = None

    def __init__(self, request: 'HttpRequest'):
        self._request = request
        self._odata = None

    def set_odata(self, odata: 'types.rest.api.ODataParams') -> None:
        self._odata = odata

    def process_get_parameters(self) -> dict[str, typing.Any]:
        """
        returns parameters based on request method
        GET parameters are understood
        """
        if self._request.method != 'GET':
            return {}

        return {k: v[0] if len(v) == 1 else v for k, v in self._request.GET.lists()}

    def process_parameters(self) -> dict[str, typing.Any]:
        """
        Returns the parameter from the request
        """
        return {}

    def get_response(self, obj: typing.Any) -> HttpResponse:
        """
        Converts an obj to a response of specific type (json, XML, ...)
        This is done using "render" method of specific type
        """
        return HttpResponse(content=self.render(obj), content_type=self.mime_type + "; charset=utf-8")

    def render(self, obj: typing.Any) -> str:
        """
        Renders an obj to the spefific type
        """
        return str(obj)

    def as_incremental(self, obj: typing.Any) -> collections.abc.Iterable[bytes]:
        """
        Renders an obj to the specific type, but in an incremental way (if possible)
        """
        yield self.render(obj).encode('utf8')

    @staticmethod
    def process_for_render(
        obj: typing.Any,
        data_transformer: collections.abc.Callable[[dict[str, typing.Any]], dict[str, typing.Any]],
    ) -> typing.Any:
        """
        Helper for renderers. Alters some types so they can be serialized correctly (as we want them to be)
        """
        match obj:
            case types.rest.BaseRestItem():
                return ContentProcessor.process_for_render(obj.as_dict(), data_transformer)
            case None | bool() | int() | float() | str():
                return obj
            case dict():
                return data_transformer(
                    {
                        k: ContentProcessor.process_for_render(v, data_transformer)
                        for k, v in typing.cast(dict[str, typing.Any], obj).items()
                        if not isinstance(v, types.rest.NotRequired)  # Skip
                    }
                )

            case DjangoPromise():
                return str(obj)  # This is for translations

            case bytes():
                return obj.decode('utf-8')

            case collections.abc.Iterable():
                return [
                    ContentProcessor.process_for_render(v, data_transformer)
                    for v in typing.cast(collections.abc.Iterable[typing.Any], obj)
                ]

            case datetime.datetime():
                return int(time.mktime(obj.timetuple()))

            case datetime.date():
                return '{}-{:02d}-{:02d}'.format(obj.year, obj.month, obj.day)

            case _:
                return str(obj)


class MarshallerProcessor(ContentProcessor):
    """
    If we have a simple marshaller for processing contents
    this class will allow us to set up a new one simply setting "marshaller"
    """

    marshaller: typing.ClassVar[typing.Any] = None

    def process_parameters(self) -> dict[str, typing.Any]:
        try:
            length = int(self._request.META.get('CONTENT_LENGTH') or '0')
            if length == 0 or not self._request.body:
                return self.process_get_parameters()

            # logger.debug('Body: >>{}<< {}'.format(self._request.body, len(self._request.body)))
            if length > consts.system.MAX_REQUEST_SIZE or length > len(self._request.body):
                raise ParametersException('Request size too big')

            res = self.marshaller.loads(self._request.body.decode('utf8'))
            logger.debug('Unmarshalled content: %s', res)

            if not isinstance(res, dict):
                raise ParametersException('Invalid content')

            return typing.cast(dict[str, typing.Any], res)
        except Exception as e:
            logger.exception('parsing %s: %s', self.mime_type, self._request.body.decode('utf8'))
            raise ParametersException(str(e))

    def render(self, obj: typing.Any) -> str:
        def none_transformer(dct: dict[str, typing.Any]) -> dict[str, typing.Any]:
            return dct
        dct_filter = none_transformer if self._odata is None else self._odata.select_filter
        return self.marshaller.dumps(ContentProcessor.process_for_render(obj, dct_filter))


# ---------------
# Json Processor
# ---------------
class JsonProcessor(MarshallerProcessor):
    """
    Provides JSON content processor
    """

    mime_type: typing.ClassVar[str] = 'application/json'
    extensions: typing.ClassVar[collections.abc.Iterable[str]] = ['json']
    marshaller: typing.ClassVar[typing.Any] = json

    def as_incremental(self, obj: typing.Any) -> collections.abc.Iterable[bytes]:
        for i in to_incremental_json(obj):
            yield i.encode('utf8')


# ---------------
# XML Processor
# ---------------
# ===============================================================================
# class XMLProcessor(MarshallerProcessor):
#     """
#     Provides XML content processor
#     """
#     mime_type = 'application/xml'
#     extensions = ['xml']
#     marshaller = xml_marshaller
# ===============================================================================


processors_list = (JsonProcessor,)
default_processor: type[ContentProcessor] = JsonProcessor
available_processors_mime_dict: dict[str, type[ContentProcessor]] = {
    cls.mime_type: cls for cls in processors_list
}
available_processors_ext_dict: dict[str, type[ContentProcessor]] = {}
for cls in processors_list:
    for ext in cls.extensions:
        available_processors_ext_dict[ext] = cls
