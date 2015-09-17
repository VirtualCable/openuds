# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

# from django.utils import simplejson as json
import ujson as json
from xml_marshaller import xml_marshaller
import datetime
import time
import types
import six
from django import http

import logging

logger = logging.getLogger(__name__)


class ParametersException(Exception):
    pass


class ContentProcessor(object):
    '''
    Process contents (request/response) so Handlers can manage them
    '''
    mime_type = None
    extensions = None

    def __init__(self, request):
        self._request = request

    def processGetParameters(self):
        '''
        returns parameters based on request method
        GET parameters are understood
        '''
        if self._request.method != 'GET':
            return {}

        return self._request.GET.copy()

    def processParameters(self):
        '''
        Returns the parameter from the request
        '''
        return ''

    def getResponse(self, obj):
        '''
        Converts an obj to a response of specific type (json, XML, ...)
        This is done using "render" method of specific type
        '''
        return http.HttpResponse(content=self.render(obj), content_type=self.mime_type + "; charset=utf-8")

    def render(self, obj):
        '''
        Renders an obj to the spefific type
        '''
        return six.text_type(obj)

    @staticmethod
    def procesForRender(obj):
        '''
        Helper for renderers. Alters some types so they can be serialized correctly (as we want them to be)
        '''
        if obj is None:
            return None
        elif isinstance(obj, (bool, int, float, six.text_type)):
            return obj
        elif isinstance(obj, long):
            return int(obj)
        elif isinstance(obj, dict):
            res = {}
            for k, v in obj.iteritems():
                res[k] = ContentProcessor.procesForRender(v)
            return res
        elif isinstance(obj, (list, tuple, types.GeneratorType)):
            res = []
            for v in obj:
                res.append(ContentProcessor.procesForRender(v))
            return res
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return int(time.mktime(obj.timetuple()))
        elif isinstance(obj, six.binary_type):
            return obj.decode('utf-8')
        return six.text_type(obj)


class MarshallerProcessor(ContentProcessor):
    '''
    If we have a simple marshaller for processing contents
    this class will allow us to set up a new one simply setting "marshaller"
    '''
    marshaller = None

    def processParameters(self):
        try:
            if len(self._request.body) == 0:
                return self.processGetParameters()
            # logger.debug('Body: >>{}<< {}'.format(self._request.body, len(self._request.body)))
            res = self.marshaller.loads(self._request.body)
            logger.debug("Unmarshalled content: {}".format(res))
            return res
        except Exception as e:
            logger.exception('parsing {}: {}'.format(self.mime_type, e))
            raise ParametersException(six.text_type(e))

    def render(self, obj):
        return self.marshaller.dumps(ContentProcessor.procesForRender(obj))
        # return json.dumps(obj)


# ---------------
# Json Processor
# ---------------
class JsonProcessor(MarshallerProcessor):
    '''
    Provides JSON content processor
    '''
    mime_type = 'application/json'
    extensions = ['json']
    marshaller = json


# ---------------
# XML Processor
# ---------------
class XMLProcessor(MarshallerProcessor):
    '''
    Provides XML content processor
    '''
    mime_type = 'application/xml'
    extensions = ['xml']
    marshaller = xml_marshaller


processors_list = (JsonProcessor, XMLProcessor)
default_processor = JsonProcessor
available_processors_mime_dict = dict((cls.mime_type, cls) for cls in processors_list)
available_processors_ext_dict = {}
for cls in processors_list:
    for ext in cls.extensions:
        available_processors_ext_dict[ext] = cls
