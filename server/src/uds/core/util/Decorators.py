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
from uds.core.util.html import checkBrowser
from uds.web import errors

from time import sleep
from functools import wraps
import warnings
import functools

import logging

__updated__ = '2014-06-11'

logger = logging.getLogger(__name__)


# Have to test this decorator before using them
def retryOnException(retries=3, delay=0):
    '''
    Decorator to retry
    '''
    def decorator(func):
        @wraps(func)
        def _wrapped_func(*args, **kwargs):
            while retries > 0:
                retries -= 1
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if retries == 0:
                        raise
                    if delay > 0:
                        sleep(delay)
        return _wrapped_func
    return decorator


# Decorator that protects pages that needs at least a browser version
# Default is to deny IE < 9
def denyBrowsers(browsers=['ie<9'], errorResponse=lambda request: errors.errorView(request, errors.BROWSER_NOT_SUPPORTED)):
    '''
    Decorator to set protection to access page
    Look for samples at uds.core.web.views
    '''
    def wrap(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            '''
            Wrapped function for decorator
            '''
            for b in browsers:
                if checkBrowser(request.META['HTTP_USER_AGENT'], b):
                    return errorResponse(request)

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return wrap

def deprecated(func):
    '''This is a decorator which can be used to mark functions
    as deprecated. It will result in a warning being emitted
    when the function is used.'''

    @functools.wraps(func)
    def new_func(*args, **kwargs):
        logger.info(
            "Call to deprecated function {0} from {1}:{2}.".format(func.__name__,
            func.func_code.co_filename,
            func.func_code.co_firstlineno + 1)
        )
        return func(*args, **kwargs)
    return new_func