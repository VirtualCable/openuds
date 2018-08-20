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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pylint: disable=too-many-public-methods

from __future__ import unicode_literals

from django.contrib.sessions.backends.db import SessionStore

from uds.core.util.Config import GlobalConfig
from uds.core.auths.auth import getRootUser
from uds.models import Authenticator
from uds.core.managers import cryptoManager

import logging

logger = logging.getLogger(__name__)

AUTH_TOKEN_HEADER = 'HTTP_X_AUTH_TOKEN'


class HandlerError(Exception):
    """
    Generic error for a REST handler
    """
    pass


class NotFound(HandlerError):
    """
    Item not found error
    """
    pass


class AccessDenied(HandlerError):
    """
    Access denied error
    """
    pass


class RequestError(HandlerError):
    """
    Request is invalid error
    """
    pass


class ResponseError(HandlerError):
    """
    Generic response error
    """
    pass


class NotSupportedError(HandlerError):
    """
    Some elements do not support some operations (as searching over an authenticator that does not supports it)
    """
    pass


class Handler(object):
    """
    REST requests handler base class
    """
    raw = False  # If true, Handler will return directly an HttpResponse Object
    name = None  # If name is not used, name will be the class name in lower case
    path = None  # Path for this method, so we can do /auth/login, /auth/logout, /auth/auths in a simple way
    authenticated = True  # By default, all handlers needs authentication
    needs_admin = False  # By default, the methods will be accessible by anyone if nothing else indicated
    needs_staff = False  # By default, staff

    # method names: 'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'
    def __init__(self, request, path, operation, params, *args, **kwargs):

        if self.needs_admin:
            self.authenticated = True  # If needs_admin, must also be authenticated

        if self.needs_staff:
            self.authenticated = True  # Same for staff members

        self._request = request
        self._path = path
        self._operation = operation
        self._params = params
        self._args = args
        self._kwargs = kwargs
        self._headers = {}
        self._authToken = None
        self._user = None
        if self.authenticated:  # Only retrieve auth related data on authenticated handlers
            try:
                self._authToken = self._request.META.get(AUTH_TOKEN_HEADER, '')
                self._session = SessionStore(session_key=self._authToken)
                if 'REST' not in self._session:
                    raise Exception()  # No valid session, so auth_token is also invalid
            except Exception:  # Couldn't authenticate
                self._authToken = None
                self._session = None

            if self._authToken is None:
                raise AccessDenied()

            if self.needs_admin and not self.getValue('is_admin'):
                raise AccessDenied()

            if self.needs_staff and not self.getValue('staff_member'):
                raise AccessDenied()

            self._user = self.getUser()

    def headers(self):
        """
        Returns the headers of the REST request (all)
        """
        return self._headers

    def header(self, headerName):
        """
        Get's an specific header name from REST request
        :param headerName: name of header to get
        """
        return self._headers.get(headerName)

    def addHeader(self, header, value):
        """
        Inserts a new header inside the headers list
        :param header: name of header to insert
        :param value: value of header
        """
        self._headers[header] = value

    def removeHeader(self, header):
        """
        Removes an specific header from the headers list
        :param header: Name of header to remove
        """
        try:
            del self._headers[header]
        except Exception:
            pass  # If not found, just ignore it

    # Auth related
    def getAuthToken(self):
        """
        Returns the authentication token for this REST request
        """
        return self._authToken

    @staticmethod
    def storeSessionAuthdata(session, id_auth, username, password, locale, platform, is_admin, staff_member, scrambler):
        """
        Stores the authentication data inside current session
        :param session: session handler (Djano user session object)
        :param id_auth: Authenticator id (DB object id)
        :param username: Name of user (login name)
        :param locale: Assigned locale
        :param is_admin: If user is considered admin or not
        :param staff_member: If is considered as staff member
        """
        if is_admin:
            staff_member = True  # Make admins also staff members :-)

        session['REST'] = {
            'auth': id_auth,
            'username': username,
            'password': cryptoManager().symCrypt(password, scrambler),  # Stores "bytes"
            'locale': locale,
            'platform': platform,
            'is_admin': is_admin,
            'staff_member': staff_member
        }

    def genAuthToken(self, id_auth, username, password, locale, platform, is_admin, staf_member, scrambler):
        """
        Generates the authentication token from a session, that is basically
        the session key itself
        :param id_auth: Authenticator id (DB object id)
        :param username: Name of user (login name)
        :param locale: Assigned locale
        :param is_admin: If user is considered admin or not
        :param staf_member: If user is considered staff member or not
        """
        session = SessionStore()
        session.set_expiry(GlobalConfig.ADMIN_IDLE_TIME.getInt())
        Handler.storeSessionAuthdata(session, id_auth, username, password, locale, platform, is_admin, staf_member, scrambler)
        session.save()
        self._authToken = session.session_key
        self._session = session
        return self._authToken

    def cleanAuthToken(self):
        """
        Cleans up the authentication token
        """
        self._authToken = None
        if self._session:
            self._session.delete()
        self._session = None

    # Session related (from auth token)
    def getValue(self, key):
        """
        Get REST session related value for a key
        """
        try:
            return self._session['REST'].get(key)
        except Exception:
            return None  # _session['REST'] does not exists?

    def setValue(self, key, value):
        """
        Set a session key value
        """
        try:
            self._session['REST'][key] = value
            self._session.accessed = True
            self._session.save()
        except Exception:
            logger.exception('Got an exception setting session value {} to {}'.format(key, value))

    def is_admin(self):
        """
        True if user of this REST request is administrator
        """
        return self.getValue('is_admin') and True or False

    def is_staff_member(self):
        """
        True if user of this REST request is member of staff
        """
        return self.getValue('staff_member') and True or False

    def getUser(self):
        """
        If user is staff member, returns his Associated user on auth
        """
        logger.debug('REST : {}'.format(self._session))
        authId = self.getValue('auth')
        username = self.getValue('username')
        # Maybe it's root user??
        if (GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.getBool(True) and
                username == GlobalConfig.SUPER_USER_LOGIN.get(True) and
                authId == -1):
            return getRootUser()
        return Authenticator.objects.get(pk=authId).users.get(name=username)
