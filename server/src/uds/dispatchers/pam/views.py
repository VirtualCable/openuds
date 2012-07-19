# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.http import HttpResponseNotAllowed, HttpResponse
from uds.core.util.Cache import Cache
import logging

logger = logging.getLogger(__name__)

# We will use the cache to "hold" the tickets valid for users

# Create your views here.
def pam(request):
    response = ''
    cache = Cache('pam')
    if request.method == 'POST':
        return HttpResponseNotAllowed(['GET'])
    if request.GET.has_key('id') & request.GET.has_key('pass'):
        # This is an "auth" request
        logger.debug("Auth request for user [{0}] and pass [{1}]".format(request.GET['id'], request.GET['pass']))
        password = cache.get(request.GET['id'])
        response = '0'
        if password == request.GET['pass']:
            response = '1'
            cache.remove(request.GET['id']) # Ticket valid for just 1 login
        
    elif request.GET.has_key('uid'):
        # This is an "get name for id" call
        logger.debug("NSS Request for id [{0}]".format(request.GET['uid']))
        response = '10000 udstmp'
    elif request.GET.has_key('name'):
        logger.debug("NSS Request for username [{0}]".format(request.GET['name']))
        response = '10000 udstmp'
    
    return HttpResponse(response, content_type='text/plain')
