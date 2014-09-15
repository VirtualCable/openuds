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

from django import http
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _, activate
from django.conf import settings
from uds.REST.handlers import Handler, HandlerError, AccessDenied, NotFound, RequestError, ResponseError

import time
import logging

logger = logging.getLogger(__name__)

__all__ = [str(v) for v in ['Handler', 'Dispatcher']]

AUTH_TOKEN_HEADER = 'X-Auth-Token'


class Dispatcher(View):
    '''
    This class is responsible of dispatching REST requests
    '''
    # This attribute will contain all paths-->handler relations, added at Initialized method
    services = {'': None}  # Will include a default /rest handler, but rigth now this will be fine

    @method_decorator(csrf_exempt)
    def dispatch(self, request, **kwargs):
        '''
        Processes the REST request and routes it wherever it needs to be routed
        '''
        logger.debug('Language in dispatcher: {0}'.format(request.LANGUAGE_CODE))
        from uds.REST import processors

        # Remove session, so response middleware do nothing with this
        del request.session
        # Now we extract method and possible variables from path
        path = kwargs['arguments'].split('/')
        del kwargs['arguments']

        # Transverse service nodes too look for path
        service = Dispatcher.services
        full_path = []
        # Last element will be
        cls = None
        while len(path) > 0:
            clean_path = path[0].split('.')[0]
            if clean_path in service:
                service = service[clean_path]
                full_path.append(path[0])
                path = path[1:]
            else:
                break
            # .json, .xml, ... will break path recursion
            if path[0].find('.') != -1:
                break

        full_path = '/'.join(full_path)
        logger.debug(full_path)

        # Here, service points to the path
        cls = service['']
        if cls is None:
            return http.HttpResponseNotFound('method not found')

        # Guess content type from content type header (post) or ".xxx" to method
        try:
            p = full_path.split('.')
            processor = processors.available_processors_ext_dict[p[1]](request)
        except Exception:
            processor = processors.available_processors_mime_dict.get(request.META.get('CONTENT_TYPE', 'json'), processors.default_processor)(request)

        # Obtain method to be invoked
        http_method = request.method.lower()

        args = path

        try:
            handler = cls(request, full_path, http_method, processor.processParameters(), *args, **kwargs)
            operation = getattr(handler, http_method)
        except processors.ParametersException as e:
            logger.debug('Path: {0}'.format(full_path))
            logger.debug('Error: {0}'.format(e))
            return http.HttpResponseServerError('Invalid parameters invoking {0}: {1}'.format(full_path, e))
        except AttributeError:
            allowedMethods = []
            for n in ['get', 'post', 'put', 'delete']:
                if hasattr(handler, n):
                    allowedMethods.append(n)
            return http.HttpResponseNotAllowed(allowedMethods)
        except AccessDenied:
            return http.HttpResponseForbidden('access denied')
        except Exception:
            logger.exception('error accessing attribute')
            logger.debug('Getting attribute {0} for {1}'.format(http_method, full_path))
            return http.HttpResponseServerError('Unexcepected error')

        # Invokes the handler's operation, add headers to response and returns
        try:
            start = time.time()
            response = operation()
            logger.debug('Execution time for method: {0}'.format(time.time() - start))

            if not handler.raw:  # Raw handlers will return an HttpResponse Object
                start = time.time()
                response = processor.getResponse(response)
            logger.debug('Execution time for encoding: {0}'.format(time.time() - start))
            for k, val in handler.headers().iteritems():
                response[k] = val
            return response
        except RequestError as e:
            return http.HttpResponseServerError(unicode(e))
        except ResponseError as e:
            return http.HttpResponseServerError(unicode(e))
        except AccessDenied as e:
            return http.HttpResponseForbidden(unicode(e))
        except NotFound as e:
            return http.HttpResponseNotFound(unicode(e))
        except HandlerError as e:
            return http.HttpResponseBadRequest(unicode(e))
        except Exception as e:
            logger.exception('Error processing request')
            return http.HttpResponseServerError(unicode(e))

    @staticmethod
    def registerSubclasses(classes):
        '''
        Try to register Handler subclasses that have not been inherited
        '''
        for cls in classes:
            if len(cls.__subclasses__()) == 0:  # Only classes that has not been inherited will be registered as Handlers
                logger.debug('Found class {0}'.format(cls))
                if cls.name is None:
                    name = cls.__name__.lower()
                else:
                    name = cls.name
                logger.debug('Adding handler {0} for method {1} in path {2}'.format(cls, name, cls.path))
                service_node = Dispatcher.services
                if cls.path is not None:
                    for k in cls.path.split('/'):
                        if service_node.get(k) is None:
                            service_node[k] = {'': None}
                        service_node = service_node[k]
                if service_node.get(name) is None:
                    service_node[name] = {'': None}

                service_node[name][''] = cls
            else:
                Dispatcher.registerSubclasses(cls.__subclasses__())

    # Initializes the dispatchers
    @staticmethod
    def initialize():
        '''
        This imports all packages that are descendant of this package, and, after that,
        it register all subclases of Handler. (In fact, it looks for packages inside "methods" package, child of this)
        '''
        import os.path
        import pkgutil
        import sys

        logger.debug('Loading Handlers')

        # Dinamycally import children of this package. The __init__.py files must register, if needed, inside ServiceProviderFactory
        package = 'methods'

        pkgpath = os.path.join(os.path.dirname(sys.modules[__name__].__file__), package)
        for _, name, _ in pkgutil.iter_modules([pkgpath]):
            __import__(__name__ + '.' + package + '.' + name, globals(), locals(), [], -1)

        Dispatcher.registerSubclasses(Handler.__subclasses__())  # @UndefinedVariable

Dispatcher.initialize()
