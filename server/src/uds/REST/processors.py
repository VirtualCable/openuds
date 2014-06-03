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
import datetime
import time
import types
from django import http

import logging

logger = logging.getLogger(__name__)


class ParametersException(Exception):
    pass


class ContentProcessor(object):
    mime_type = None
    extensions = None

    def __init__(self, request):
        self._request = request

    def processGetParameters(self):
        if self._request.method != 'GET':
            return {}

        return self._request.GET.copy()

    def processParameters(self):
        return ''

    def getResponse(self, obj):
        return http.HttpResponse(content=self.render(obj), content_type=self.mime_type + "; charset=utf-8")

    def render(self, obj):
        return unicode(obj)

    @staticmethod
    def procesForRender(obj):
        '''
        Helper for renderers. Alters some types so they can be serialized correctly (as we want them to be)
        '''
        if type(obj) in (bool, int, float, unicode):
            return obj
        elif isinstance(obj, long):
            return int(obj)
        elif isinstance(obj, dict):
            res = {}
            for k, v in obj.iteritems():
                res[k] = ContentProcessor.procesForRender(v)
            return res
        elif type(obj) in (list, tuple, types.GeneratorType):
            res = []
            for v in obj:
                res.append(ContentProcessor.procesForRender(v))
            return res
        elif isinstance(obj, datetime.datetime):
            return  int(time.mktime(obj.timetuple()))
        elif isinstance(obj, str):
            return obj.decode('utf-8')
        return unicode(obj)


# ---------------
# Json Processor
# ---------------
class JsonProcessor(ContentProcessor):
    mime_type = 'application/json'
    extensions = ['json']

    def processParameters(self):
        try:
            if len(self._request.body) == 0:
                return self.processGetParameters()
            res = json.loads(self._request.body)
            logger.debug(res)
            return res
        except Exception as e:
            logger.error('parsing json: {0}'.format(e))
            raise ParametersException(unicode(e))

    def render(self, obj):
        return json.dumps(ContentProcessor.procesForRender(obj))
        # return json.dumps(obj)


# ---------------
# XML Processor
# ---------------
class XMLProcessor(ContentProcessor):
    mime_type = 'application/xml'
    extensions = ['xml']

    def processParameters(self):
        return ''

processors_list = (JsonProcessor, XMLProcessor)
default_processor = JsonProcessor
available_processors_mime_dict = dict((cls.mime_type, cls) for cls in processors_list)
available_processors_ext_dict = {}
for cls in processors_list:
    for ext in cls.extensions:
        available_processors_ext_dict[ext] = cls
