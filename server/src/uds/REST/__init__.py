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
from handlers import Handler, HandlerError, AccessDenied

import logging

logger = logging.getLogger(__name__)

__all__ = [ str(v) for v  in ['Handler', 'Dispatcher'] ]

class Dispatcher(View):
    services = { '' : None } # Will include a default /rest handler, but rigth now this will be fine
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, **kwargs):
        import processors
        
        # Remove session, so response middelwares do nothing with this
        del request.session
        # Now we extract method and posible variables from path
        path = kwargs['arguments'].split('/')
        del kwargs['arguments']
        
        # Transverse service nodes too look for path
        service = Dispatcher.services
        full_path = []
        # Last element will be
        do_break = False 
        cls = None
        while len(path) > 0 and not do_break:
            # .json, .xml, ... will break path recursion
            do_break = path[0].find('.') != -1
            clean_path = path[0].split('.')[0]
            if service.has_key(clean_path):
                service = service[clean_path]
                full_path.append(path[0])
                path = path[1:]
            else:
                break

        full_path = '/'.join(full_path)
        logger.debug(full_path)

        cls = service['']
        if cls is None:
            return http.HttpResponseNotFound('method not found')
            
        
        # Guess content type from content type header or ".xxx" to method
        try:
            p = full_path.split('.')
            processor = processors.available_processors_ext_dict[p[1]](request)
        except:
            processor = processors.available_processors_mime_dict.get(request.META['CONTENT_TYPE'], processors.default_processor)(request)
            

        # Obtain method to be invoked
        http_method = request.method.lower()
        
        args = path
        
        # Inspect
        lang = None
        if len(args) > 0:
            for l in settings.LANGUAGES:
                if args[-1] == l[0]:
                    lang = l[0]
                    activate(lang)
                    logger.error('Found lang {0}'.format(l))
                    args = args[:-1]
                    break
        # Instantiate method handler and locate http_method dispatcher
        try:
            handler = cls(request, full_path, http_method, processor.processParameters(), *args, **kwargs)
            # If no lang on request, try to get the one from 
            if lang is None:
                activate(handler.getValue('locale'))
            else:
                handler.setValue('locale', lang) # Update Locale if request had one
            
            operation = getattr(handler, http_method)
        except processors.ParametersException as e:
            return http.HttpResponseServerError('Invalid parameters invoking {0}: {1}'.format(path[0], e))
        except AttributeError:
            allowedMethods = []
            for n in ['get', 'post', 'put', 'delete']:
                if hasattr(handler, n):
                    allowedMethods.append(n)
            return http.HttpResponseNotAllowed(allowedMethods)
        except AccessDenied:
            return http.HttpResponseForbidden('access denied')
        except:
            logger.exception('error accessing attribute')
            logger.debug('Getting attribute {0} for {1}'.format(http_method, full_path))
            return http.HttpResponseServerError('Unexcepected error')
        
            
        # Invokes the handler's operation, add headers to response and returns
        try:
            response = processor.getResponse(operation())
            for k, v in handler.headers().iteritems():
                response[k] = v
            return response
        except HandlerError as e:
            return http.HttpResponseBadRequest(unicode(e))
        except Exception as e:
            logger.exception('Error processing request')
            return http.HttpResponseServerError(unicode(e))

    # Initializes the dispatchers
    @staticmethod
    def initialize():
        '''
        This imports all packages that are descendant of this package, and, after that,
        it register all subclases of Handler. (In fact, it looks for packages inside "methods" package, child of this)
        '''
        import os.path, pkgutil
        import sys
        
        # Dinamycally import children of this package. The __init__.py files must register, if needed, inside ServiceProviderFactory
        package = 'methods'
        
        pkgpath = os.path.join(os.path.dirname(sys.modules[__name__].__file__), package)
        for _, name, _ in pkgutil.iter_modules([pkgpath]):
            __import__(__name__ + '.' + package +  '.' + name, globals(), locals(), [], -1)
            
        for cls in Handler.__subclasses__():  # @UndefinedVariable
            # Skip ClusteredServiceProvider
            if cls.name is None:
                name = cls.__name__.lower()
            else:
                name = cls.name
            logger.debug('Adding handler {0} for method {1} in path {2}'.format(cls, name, cls.path))
            service_node = Dispatcher.services
            if cls.path is not None:
                for k in cls.path.split('/'):
                    if service_node.get(k) is None:
                        service_node[k] = { '' : None }
                    service_node = service_node[k]
            if service_node.get(name) is None:
                service_node[name] = { '' : None }
                   
            service_node[name][''] = cls
        
Dispatcher.initialize()
