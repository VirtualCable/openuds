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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import os.path
import pkgutil
import sys
import importlib
import logging
import typing

from django import http
from django.views.generic.base import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.translation import ugettext as _
from uds.core import VERSION, VERSION_STAMP

from .handlers import (
    Handler,
    HandlerError,
    AccessDenied,
    NotFound,
    RequestError,
    ResponseError,
    NotSupportedError
)

from . import processors

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from  uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)

__all__ = ['Handler', 'Dispatcher']

AUTH_TOKEN_HEADER = 'X-Auth-Token'


class Dispatcher(View):
    """
    This class is responsible of dispatching REST requests
    """
    # This attribute will contain all paths--> handler relations, filled at Initialized method
    services: typing.ClassVar[typing.Dict[str, typing.Any]] = {'': None}  # Will include a default /rest handler, but rigth now this will be fine

    # pylint: disable=too-many-locals, too-many-return-statements, too-many-branches, too-many-statements
    @method_decorator(csrf_exempt)
    def dispatch(self, request: 'ExtendedHttpRequest', *args, **kwargs):
        """
        Processes the REST request and routes it wherever it needs to be routed
        """
        # Remove session from request, so response middleware do nothing with this
        del request.session

        # Now we extract method and possible variables from path
        path: typing.List[str] = kwargs['arguments'].split('/')
        del kwargs['arguments']

        # Transverse service nodes, so we can locate class processing this path
        service = Dispatcher.services
        full_path_lst: typing.List[str] = []
        # Guess content type from content type header (post) or ".xxx" to method
        content_type: str = request.META.get('CONTENT_TYPE', 'json')

        while path:
            # .json, .xml, .anything will break path recursion
            if path[0].find('.') != -1:
                content_type = path[0].split('.')[1]

            clean_path = path[0].split('.')[0]
            if not clean_path:  # Skip empty path elements, so /x/y == /x////y for example (due to some bugs detected on some clients)
                path = path[1:]
                continue

            if clean_path in service:
                service = service[clean_path]
                full_path_lst.append(path[0])
                path = path[1:]
            else:
                break

        full_path = '/'.join(full_path_lst)
        logger.debug("REST request: %s (%s)", full_path, content_type)

        # Here, service points to the path
        cls: typing.Optional[typing.Type[Handler]] = service['']
        if cls is None:
            return http.HttpResponseNotFound('Method not found', content_type="text/plain")

        processor = processors.available_processors_ext_dict.get(content_type, processors.default_processor)(request)

        # Obtain method to be invoked
        http_method: str = request.method.lower() if request.method else ''

        # Path here has "remaining" path, that is, method part has been removed
        args = tuple(path)

        handler = None

        try:
            handler = cls(request, full_path, http_method, processor.processParameters(), *args, **kwargs)
            operation: typing.Callable[[], typing.Any] = getattr(handler, http_method)
        except processors.ParametersException as e:
            logger.debug('Path: %s', full_path)
            logger.debug('Error: %s', e)
            return http.HttpResponseServerError('Invalid parameters invoking {0}: {1}'.format(full_path, e), content_type="text/plain")
        except AttributeError:
            allowedMethods = []
            for n in ['get', 'post', 'put', 'delete']:
                if hasattr(handler, n):
                    allowedMethods.append(n)
            return http.HttpResponseNotAllowed(allowedMethods, content_type="text/plain")
        except AccessDenied:
            return http.HttpResponseForbidden('access denied', content_type="text/plain")
        except Exception:
            logger.exception('error accessing attribute')
            logger.debug('Getting attribute %s for %s', http_method, full_path)
            return http.HttpResponseServerError('Unexcepected error', content_type="text/plain")

        # Invokes the handler's operation, add headers to response and returns
        try:
            response = operation()

            if not handler.raw:  # Raw handlers will return an HttpResponse Object
                response = processor.getResponse(response)
            # Set response headers
            response['UDS-Version'] = f'{VERSION};{VERSION_STAMP}'
            for k, val in handler.headers().items():
                response[k] = val
            return response
        except RequestError as e:
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except ResponseError as e:
            return http.HttpResponseServerError(str(e), content_type="text/plain")
        except NotSupportedError as e:
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except AccessDenied as e:
            return http.HttpResponseForbidden(str(e), content_type="text/plain")
        except NotFound as e:
            return http.HttpResponseNotFound(str(e), content_type="text/plain")
        except HandlerError as e:
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except Exception as e:
            logger.exception('Error processing request')
            return http.HttpResponseServerError(str(e), content_type="text/plain")

    @staticmethod
    def registerSubclasses(classes: typing.List[typing.Type[Handler]]):
        """
        Try to register Handler subclasses that have not been inherited
        """
        for cls in classes:
            if not cls.__subclasses__():  # Only classes that has not been inherited will be registered as Handlers
                if not cls.name:
                    name = cls.__name__.lower()
                else:
                    name = cls.name
                logger.debug('Adding handler %s for method %s in path %s', cls, name, cls.path)
                service_node = Dispatcher.services  # Root path
                if cls.path:
                    for k in cls.path.split('/'):
                        if k not in service_node:
                            service_node[k] = {'': None}
                        service_node = service_node[k]
                if name not in service_node:
                    service_node[name] = {'': None}

                service_node[name][''] = cls
            else:
                Dispatcher.registerSubclasses(cls.__subclasses__())

    # Initializes the dispatchers
    @staticmethod
    def initialize():
        """
        This imports all packages that are descendant of this package, and, after that,
        it register all subclases of Handler. (In fact, it looks for packages inside "methods" package, child of this)
        """
        logger.info('Initializing REST Handlers')

        # Dinamycally import children of this package.
        package = 'methods'

        pkgpath = os.path.join(os.path.dirname(sys.modules[__name__].__file__), package)
        for _, name, _ in pkgutil.iter_modules([pkgpath]):
            # __import__(__name__ + '.' + package + '.' + name, globals(), locals(), [], 0)
            importlib.import_module( __name__ + '.' + package + '.' + name)  # import module

        importlib.invalidate_caches()

        Dispatcher.registerSubclasses(Handler.__subclasses__())  # @UndefinedVariable


Dispatcher.initialize()
