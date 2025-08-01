# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
import dataclasses
import logging
import sys
import typing
import collections.abc
import traceback

from django import http
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View

from uds.core.types.rest import HandlerNode
from uds.core import consts, exceptions, types
from uds.core.util import modfinder
from uds.core.util.model import sql_stamp_seconds

from . import processors, log
from .handlers import Handler
from .model import DetailHandler

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser

logger = logging.getLogger(__name__)

__all__ = ['Handler', 'Dispatcher']


class Dispatcher(View):
    """
    This class is responsible of dispatching REST requests
    """

    # This attribute will contain all paths--> handler relations, filled at Initialized method
    base_handler_node: typing.ClassVar[HandlerNode] = HandlerNode('', None, None, {})

    @method_decorator(csrf_exempt)
    def dispatch(
        self, request: 'http.request.HttpRequest', *args: typing.Any, **kwargs: typing.Any
    ) -> 'http.HttpResponse':
        """
        Processes the REST request and routes it wherever it needs to be routed
        """
        request = typing.cast('ExtendedHttpRequestWithUser', request)  # Reconverting to typed request
        if not hasattr(request, 'user'):
            raise exceptions.rest.HandlerError('Request does not have a user, cannot process request')

        # Remove session from request, so response middleware do nothing with this
        del request.session

        # Now we extract method and possible variables from path
        # path: list[str] = kwargs['arguments'].split('/')
        path = kwargs['arguments']
        del kwargs['arguments']

        # # Transverse service nodes, so we can locate class processing this path
        # service = Dispatcher.services
        # full_path_lst: list[str] = []
        # # Guess content type from content type header (post) or ".xxx" to method
        content_type: str = request.META.get('CONTENT_TYPE', 'application/json').split(';')[0]

        handler_node = Dispatcher.base_handler_node.find_path(path)
        if not handler_node:
            return http.HttpResponseNotFound('Service not found', content_type="text/plain")

        logger.debug("REST request: %s (%s)", handler_node, handler_node.full_path())

        # Now, service points to the class that will process the request
        # We get the '' node, that is the "current" node, and get the class from it
        cls: typing.Optional[type[Handler]] = handler_node.handler
        if not cls:
            return http.HttpResponseNotFound('Method not found', content_type="text/plain")

        processor = processors.available_processors_mime_dict.get(content_type, processors.default_processor)(
            request
        )

        # Obtain method to be invoked
        http_method: str = request.method.lower() if request.method else ''
        # ensure method is recognized
        if http_method not in ('get', 'post', 'put', 'delete'):
            return http.HttpResponseNotAllowed(['GET', 'POST', 'PUT', 'DELETE'], content_type="text/plain")

        # Path here has "remaining" path, that is, method part has been removed
        args = path[len(handler_node.full_path()) :].split('/')[
            1:
        ]  # First element is always empty, so we skip it

        handler: typing.Optional[Handler] = None

        try:
            handler = cls(
                request,
                handler_node.full_path(),
                http_method,
                processor.process_parameters(),
                *args,
                **kwargs,
            )
            operation: collections.abc.Callable[[], typing.Any] = getattr(handler, http_method)
        except processors.ParametersException as e:
            logger.debug(
                'Path: %s',
            )
            logger.debug('Error: %s', e)

            log.log_operation(handler, 400, types.log.LogLevel.ERROR)
            return http.HttpResponseBadRequest(
                f'Invalid parameters invoking {handler_node.full_path()}: {e}',
                content_type="text/plain",
            )
        except AttributeError:
            allowed_methods: list[str] = [n for n in ['get', 'post', 'put', 'delete'] if hasattr(handler, n)]
            log.log_operation(handler, 405, types.log.LogLevel.ERROR)
            return http.HttpResponseNotAllowed(allowed_methods, content_type="text/plain")
        except exceptions.rest.AccessDenied:
            log.log_operation(handler, 403, types.log.LogLevel.ERROR)
            return http.HttpResponseForbidden('access denied', content_type="text/plain")
        except Exception:
            log.log_operation(handler, 500, types.log.LogLevel.ERROR)
            logger.exception('error accessing attribute')
            logger.debug('Getting attribute %s for %s', http_method, handler_node.full_path())
            return http.HttpResponseServerError('Unexcepected error', content_type="text/plain")

        # Invokes the handler's operation, add headers to response and returns
        try:
            response = operation()

            # If response is an HttpResponse object, return it directly
            if not isinstance(response, http.HttpResponse):
                # If it is a generator, produce an streamed incremental response
                if isinstance(response, collections.abc.Generator):
                    response = typing.cast(
                        'http.HttpResponse',
                        http.StreamingHttpResponse(
                            processor.as_incremental(response),
                            content_type="application/json",
                        ),
                    )
                else:
                    response = processor.get_response(response)
            # Set response headers
            response['UDS-Version'] = f'{consts.system.VERSION};{consts.system.VERSION_STAMP}'
            response['Response-Stamp'] = sql_stamp_seconds()
            for k, val in handler.headers().items():
                response[k] = val

            # Log de operation on the audit log for admin
            # Exceptiol will also be logged, but with ERROR level
            log.log_operation(handler, response.status_code, types.log.LogLevel.INFO)
            return response
        except exceptions.rest.RequestError as e:
            log.log_operation(handler, 400, types.log.LogLevel.ERROR)
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except exceptions.rest.ResponseError as e:
            log.log_operation(handler, 500, types.log.LogLevel.ERROR)
            return http.HttpResponseServerError(str(e), content_type="text/plain")
        except exceptions.rest.NotSupportedError as e:
            log.log_operation(handler, 501, types.log.LogLevel.ERROR)
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except exceptions.rest.AccessDenied as e:
            log.log_operation(handler, 403, types.log.LogLevel.ERROR)
            return http.HttpResponseForbidden(str(e), content_type="text/plain")
        except exceptions.rest.NotFound as e:
            log.log_operation(handler, 404, types.log.LogLevel.ERROR)
            return http.HttpResponseNotFound(str(e), content_type="text/plain")
        except exceptions.rest.HandlerError as e:
            log.log_operation(handler, 500, types.log.LogLevel.ERROR)
            return http.HttpResponseBadRequest(str(e), content_type="text/plain")
        except Exception as e:
            log.log_operation(handler, 500, types.log.LogLevel.ERROR)
            # Get ecxeption backtrace
            trace_back = traceback.format_exc()
            logger.error('Exception processing request: %s', handler_node.full_path())
            for i in trace_back.splitlines():
                logger.error('* %s', i)

            return http.HttpResponseServerError(str(e), content_type="text/plain")

    @staticmethod
    def register_handler(type_: type[Handler]) -> None:
        """
        Method to register a class as a REST service
        param type_: Class to be registered
        """
        if not type_.NAME:
            name = sys.intern(type_.__name__.lower())
        else:
            name = type_.NAME

        # Fill the service_node tree with the class
        service_node = Dispatcher.base_handler_node  # Root path
        # If path, ensure that the path exists on the tree
        if type_.PATH:
            logger.info('Path: /%s/%s', type_.PATH, name)
            for k in type_.PATH.split('/'):
                intern_k = sys.intern(k)
                if intern_k not in service_node.children:
                    service_node.children[intern_k] = HandlerNode(k, None, service_node, {})
                service_node = service_node.children[intern_k]
        else:
            logger.info('Path: /%s', name)

        if name not in service_node.children:
            service_node.children[name] = HandlerNode(name, None, service_node, {})

        service_node.children[name] = dataclasses.replace(service_node.children[name], handler=type_)

    # Initializes the dispatchers
    @staticmethod
    def initialize() -> None:
        """
        This imports all packages that are descendant of this package, and, after that,
        it register all subclases of Handler. (In fact, it looks for packages inside "methods" package, child of this)
        """
        logger.info('Initializing REST Handlers')
        # Our parent module "REST", because we are in "dispatcher"
        module_name = __name__[: __name__.rfind('.')]

        def checker(x: type[Handler]) -> bool:
            # only register if final class, no classes that have subclasses
            logger.debug(
                'Checking %s - %s - %s', x.__name__, issubclass(x, DetailHandler), x.__subclasses__() == []
            )
            return not issubclass(x, DetailHandler) and not x.__subclasses__()

        # Register all subclasses of Handler
        modfinder.dynamically_load_and_register_packages(
            Dispatcher.register_handler,
            Handler,
            module_name=module_name,
            checker=checker,
            package_name='methods',
        )


Dispatcher.initialize()
