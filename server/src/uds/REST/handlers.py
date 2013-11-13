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
from django.contrib.sessions.backends.db import SessionStore
from django.utils.translation import activate
from django.conf import settings

from uds.core.util.Config import GlobalConfig

import logging

logger = logging.getLogger(__name__)

AUTH_TOKEN_HEADER = 'HTTP_X_AUTH_TOKEN'

class HandlerError(Exception):
    pass

class AccessDenied(HandlerError):
    pass

class Handler(object):
    raw = False # If true, Handler will return directly an HttpResponse Object
    name = None # If name is not used, name will be the class name in lower case
    path = None # Path for this method, so we can do /auth/login, /auth/logout, /auth/auths in a simple way
    authenticated = True # By default, all handlers needs authentication
    needs_admin = False # By default, the methods will be accessible by anyone if nothine else indicated
    needs_staff = False # By default, staff 
    
    # method names: 'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'
    def __init__(self, request, path, operation, params, *args, **kwargs):
        
        if self.needs_admin:
            self.authenticated = True # If needs_admin, must also be authenticated
            
        if self.needs_staff:
            self.authenticated = True # Same for staff members
            
        self._request = request
        self._path = path
        self._operation = operation
        self._params = params
        self._args = args
        self._kwargs = kwargs
        self._headers = {}
        self._authToken = None
        if self.authenticated: # Only retrieve auth related data on authenticated handlers
            try:
                self._authToken = self._request.META.get(AUTH_TOKEN_HEADER, '')
                self._session = SessionStore(session_key = self._authToken)
                if not self._session.has_key('REST'):
                    raise Exception() # No valid session, so auth_token is also invalid
            except:
                if settings.DEBUG: # Right now all users are valid
                    self.genAuthToken(-1, 'root', 'es', True, True)
                else:
                    self._authToken = None
                    self._session = None
                
            if self._authToken is None:
                raise AccessDenied()
            
            if self.needs_admin and not self.getValue('is_admin'):
                raise AccessDenied()
            
            if self.needs_staff and not self.getValue('staff_member'):
                raise AccessDenied()
        
    def headers(self):
        return self._headers
    
    def header(self, header_):
        return self._headers.get(header_)
    
    def addHeader(self, header, value):
        self._headers[header] = value
        
    def removeHeader(self, header):
        try:
            del self._headers[header]
        except:
            pass
        
    # Auth related
    def getAuthToken(self):
        return self._authToken
    
    @staticmethod
    def storeSessionAuthdata(session, id_auth, username, locale, is_admin, staff_member):
        if is_admin:
            staff_member = True # Make admins also staff members :-)
            
        session['REST'] = { 'auth': id_auth, 'username': username, 
                           'locale': locale,  'is_admin': is_admin, 
                           'staff_member': staff_member }
        
    
    def genAuthToken(self, id_auth, username, locale, is_admin, staf_member):
        session = SessionStore()
        session.set_expiry(GlobalConfig.ADMIN_IDLE_TIME.getInt())
        Handler.storeSessionAuthdata(session, id_auth, username, locale, is_admin, staf_member)
        session.save()
        self._authToken = session.session_key
        self._session = session
        return self._authToken
    
    def cleanAuthToken(self):
        self._authToken = None
        if self._session:
            self._session.delete()
        self._session = None
    
    # Session related (from auth token)
    def getValue(self, key):
        try:
            return self._session['REST'].get(key)
        except:
            return None
        
    def setValue(self, key, value):
        try:
            self._session['REST'][key] = value
            self._session.accessed = True
            self._session.save()
        except:
            pass
