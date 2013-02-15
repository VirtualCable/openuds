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

from django.utils.translation import ugettext as _, activate
from django.contrib.sessions.backends.db import SessionStore
from uds.models import Authenticator
from uds.xmlrpc.util.Exceptions import AuthException
from uds.core.util.Config import GlobalConfig
from uds.core.util import log
from uds.core.auths.auth import authenticate, getIp
from functools import wraps
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

ADMIN_AUTH = '#'

CLIENT_VERSION_REQUIRED = '1.1.0'

class Credentials(object):
    '''
    Represents a valid credential from a user connected to administration.
    '''
    def __init__(self, request, session, credential_key):
        self.request = request
        self.idAuth = session['idAuth']
        self.isAdmin = session['isAdmin']
        self.user = session['username']
        self.locale = session['locale']
        self.key = credential_key
        
    def __unicode__(self):
        return "authId: {0}, isAdmin: {1}, user: {2}, locale: {3}, key: {4}".format(self.idAuth, self.isAdmin, self.user, self.locale, self.key)
    
    def __str__(self):
        return "authId: {0}, isAdmin: {1}, user: {2}, locale: {3}, key: {4}".format(self.idAuth, self.isAdmin, self.user, self.locale, self.key)
    
    def logout(self):
        '''
        Logout administration user
        '''
        logger.info('Logged out admin user {0}'.format(self))
        
        if self.idAuth == ADMIN_AUTH: # Root administrator does nothing on logout
            return ''
        try:
            a = Authenticator.objects.get(pk=self.idAuth).getInstance()
            log.doLog(self.user, log.INFO, 'Logged out from administration', log.WEB)
            return a.logout(self.user)
        except Exception:
            logger.exception('Exception at logout (managed)')
            
        return ''
        
    

def makeCredentials(idAuth, username, locale, isAdmin):
    session = SessionStore()
    session.set_expiry(GlobalConfig.ADMIN_IDLE_TIME.getInt())
    session['idAuth'] = idAuth
    session['username'] = username
    session['locale'] = locale
    session['isAdmin'] = isAdmin
    session.save()
    return { 'credentials' : session.session_key, 'versionRequired' : CLIENT_VERSION_REQUIRED, 'url' : settings.STATIC_URL + "bin/UDSAdminSetup.exe",
             'urlLinux' : settings.STATIC_URL + "bin/UDSAdminSetup.tar.gz", 'isAdmin' : isAdmin }

# Decorator for validate credentials
def needs_credentials(xmlrpc_func):
    '''
    Validates the credentials
    '''
    @wraps(xmlrpc_func)
    def _wrapped_xmlrcp_func(credentials, *args, **kwargs):
        # We expect that request is passed in as last argument ALWAYS (look at views)
        args = list(args)
        request = args.pop() # Last argumment is request
        args = tuple(args)
        logger.debug('Checkin credentials {0} for function {1}'.format(credentials, xmlrpc_func.__name__))
        cred = validateCredentials(request, credentials) 
        if cred is not None:
            logger.debug('Credentials valid, executing')
            return xmlrpc_func(cred, *args, **kwargs)
        raise AuthException(_('Credentials no longer valid'))
    return _wrapped_xmlrcp_func


def validateCredentials(request, credentials):
    '''
    Validates the credentials of an user
    :param credentials:
    '''
    session = SessionStore(session_key = credentials)
    if session.exists(credentials) is False:
        return None
    if session.has_key('idAuth') is False:
        return None
    activate(session['locale'])
    logger.debug('Locale activated')
    # Updates the expire key, this is the slow part as we can see at debug log, better if we can only update the expire_key this takes 80 ms!!!
    session.save()
    logger.debug('Session updated')
    return Credentials(request, session, credentials )


def invalidateCredentials(credentials):
    session = SessionStore(session_key = credentials.key)
    session.delete()


def getAdminAuths(locale):
    '''
    Returns the authenticators 
    '''
    activate(locale)
    res = []
    for a in Authenticator.all():
        if a.getType().isCustom() is False:
            res.append( { 'id' : str(a.id), 'name' : a.name } )
    return res + [ {'id' : ADMIN_AUTH, 'name' : _('Administration') }] 
    

# Xmlrpc functions
def login(username, password, idAuth, locale, request):
    '''
    Validates the user/password credentials, assign to it the specified locale for this session and returns a credentials response
    '''
    
    getIp(request)
    
    logger.info("Validating user {0} with authenticator {1} with locale {2}".format(username, idAuth, locale))
    activate(locale)
    if idAuth == ADMIN_AUTH:
        if GlobalConfig.SUPER_USER_LOGIN.get(True) == username and GlobalConfig.SUPER_USER_PASS.get(True) == password:
            return makeCredentials(idAuth, username, locale, True)
        else:
            raise AuthException(_('Invalid credentials'))
    try:
        auth = Authenticator.objects.get(pk=idAuth)
        user = authenticate(username, password, auth)
    except Exception:
        raise AuthException(_('Invalid authenticator'))
    
    if user is None:
        log.doLog(auth, log.ERROR, 'Invalid credentials for {0} from {1}'.format(username, request.ip), log.ADMIN)
        try:
            user = auth.users.get(name=username)
            log.doLog(user, log.ERROR, 'Invalid credentials from {0}'.format(request.ip), log.ADMIN)
        except:
            pass
        raise AuthException(_('Access denied'))
    
    if user.staff_member is False:
        log.doLog(auth, log.ERROR, 'Access denied from {1}. User {0} is not membef of staff'.format(username, request.ip), log.ADMIN)
        log.doLog(user, log.ERROR, 'Access denied from {0}. This user is not membef of staff'.format(request.ip), log.ADMIN)
        
        raise AuthException(_('Access denied'))
    
    log.doLog(auth, log.INFO, 'Access granted to user {0} from {1} to administration'.format(username, request.ip), log.ADMIN)
    log.doLog(user, log.INFO, 'Access granted from {0} to administration'.format(request.ip), log.ADMIN)
    
    return makeCredentials(idAuth, username, locale, user.is_admin)
        

@needs_credentials
def logout(credentials):
    '''
    Logs out and administration user
    '''
    ret = credentials.logout() or ''
    invalidateCredentials(credentials)
    return ret

def registerAdminAuthFunctions(dispatcher):
    dispatcher.register_function(login, 'login')
    dispatcher.register_function(getAdminAuths, 'getAdminAuths')
    dispatcher.register_function(logout, 'logout')
