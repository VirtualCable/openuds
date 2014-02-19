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
Provides useful functions for authenticating, used by web interface.


.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from functools import wraps
from django.http import HttpResponseRedirect, HttpResponseForbidden
from django.utils.translation import get_language

from django.utils.translation import ugettext as _
from uds.core.util.Config import GlobalConfig
from uds.core.util import log
from uds.core import auths
from uds.core.managers.CryptoManager import CryptoManager
from uds.core.util.State import State
from uds.models import User

import logging

__updated__ = '2014-02-19'

logger = logging.getLogger(__name__)
authLogger = logging.getLogger('authLog')

USER_KEY = 'uk'
PASS_KEY = 'pk'
ROOT_ID = -20091204  # Any negative number will do the trick


def getRootUser():
    from uds.models import Authenticator
    u = User(id=ROOT_ID, name=GlobalConfig.SUPER_USER_LOGIN.get(True), real_name=_('System Administrator'), state=State.ACTIVE, staff_member=True, is_admin=True)
    u.manager = Authenticator()
    u.getGroups = lambda: []
    u.updateLastAccess = lambda: None
    u.logout = lambda: None
    return u


def getIp(request, translateProxy=True):
    '''
    Obtains the IP of a Django Request, even behind a proxy

    Returns the obtained IP, that is always be a valid ip address.
    '''
    try:
        if translateProxy is False:
            raise KeyError()  # Do not allow HTTP_X_FORWARDED_FOR
        request.ip = request.META['HTTP_X_FORWARDED_FOR'].split(",")[0]
    except KeyError:
        request.ip = request.META['REMOTE_ADDR']
    return request.ip


# Decorator to make easier protect pages that needs to be logged in
def webLoginRequired(view_func):
    '''
    Decorator to set protection to access page
    Look for samples at uds.core.web.views
    '''
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        '''
        Wrapped function for decorator
        '''
        user = request.session.get(USER_KEY)
        if user is not None:
            try:
                if user == ROOT_ID:
                    user = getRootUser()
                else:
                    user = User.objects.get(pk=user)
            except User.DoesNotExist:
                user = None
        if user is None:
            url = request.build_absolute_uri(GlobalConfig.LOGIN_URL.get())
            if GlobalConfig.REDIRECT_TO_HTTPS.getBool() is True:
                url = url.replace('http://', 'https://')
            logger.debug('No user found, redirecting to {0}'.format(url))
            return HttpResponseRedirect(url)
        # Refresh session duration
        # request.session.set_expiry(GlobalConfig.USER_SESSION_LENGTH.getInt())
        request.user = user
        getIp(request)
        return view_func(request, *args, **kwargs)
    return _wrapped_view


# Decorator to protect pages that needs to be accessed from "trusted sites"
def trustedSourceRequired(view_func):
    '''
    Decorator to set protection to access page
    look for sample at uds.dispatchers.pam
    '''
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        '''
        Wrapped function for decorator
        '''
        from uds.core.util import net
        getIp(request, False)
        if net.ipInNetwork(request.ip, GlobalConfig.TRUSTED_SOURCES.get(True)) is False:
            return HttpResponseForbidden()
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def __registerUser(authenticator, authInstance, username):
    '''
    Check if this user already exists on database with this authenticator, if don't, create it with defaults
    This will work correctly with both internal or externals cause we first authenticate the user, if internal and user do not exists in database
    authenticate will return false, if external and return true, will create a reference in database
    '''
    username = authInstance.transformUsername(username)
    logger.debug('Transformed username: {0}'.format(username))

    usr = authenticator.getOrCreateUser(username, authInstance.getRealName(username))
    if usr is not None and State.isActive(usr.state):
        # Now we update database groups for this user
        usr.getManager().recreateGroups(usr)
        return usr

    return None


def authenticate(username, password, authenticator, useInternalAuthenticate=False):
    '''
    Given an username, password and authenticator, try to authenticate user
    @param username: username to authenticate
    @param password: password to authenticate this user
    @param authenticator: Authenticator (database object) used to authenticate with provided credentials
    @param useInternalAuthenticate: If True, tries to authenticate user using "internalAuthenticate". If false, it uses "authenticate".
                                    This is so because in some situations we may want to use a "trusted" method (internalAuthenticate is never invoked directly from web)
    @return: None if authentication fails, User object (database object) if authentication is o.k.
    '''
    logger.debug('Authenticating user {0} with authenticator {1}'.format(username, authenticator))

    # If global root auth is enabled && user/password is correct,
    if GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.getBool(True) and username == GlobalConfig.SUPER_USER_LOGIN.get(True) and password == GlobalConfig.SUPER_USER_PASS.get(True):
        return getRootUser()

    gm = auths.GroupsManager(authenticator)
    authInstance = authenticator.getInstance()
    if useInternalAuthenticate is False:
        res = authInstance.authenticate(username, password, gm)
    else:
        res = authInstance.internalAuthenticate(username, password, gm)

    if res is False:
        return None

    logger.debug('Groups manager: {0}'.format(gm))

    # If do not have any valid group
    if gm.hasValidGroups() is False:
        return None

    return __registerUser(authenticator, authInstance, username)


def authenticateViaCallback(authenticator, params):
    '''
    Given an username, this method will get invoked whenever the url for a callback
    for an authenticator is requested.

    The idea behind this is that, with authenticators that are based on url redirections
    (SSO auths), we provide a mechanism to allow the authenticator to login the user.

    This will:
       * Check that the authenticator supports a callback, raise an error if it
         doesn't support it.
       * Invoke authenticator callback, and expects, on exit, a valid username.
         If it gets None or '', it will raise an error.
       * Register user inside uds if necesary, will invoke in the process
         **getRealUsername** to get it, so keep it wher you can recover it.
       * Update user group membership using Authenticator getGroups, so, in your
         callbacks, remember to store (using provided environment storage, for example)
         the groups of this user so your getGroups will work correctly.
    '''
    gm = auths.GroupsManager(authenticator)
    authInstance = authenticator.getInstance()

    # If there is no callback for this authenticator...
    if authInstance.authCallback == auths.Authenticator.authCallback:
        raise auths.Exceptions.InvalidAuthenticatorException()

    username = authInstance.authCallback(params, gm)

    if username is None or username == '' or gm.hasValidGroups() is False:
        raise auths.Exceptions.InvalidUserException('User don\'t has access to UDS')

    return __registerUser(authenticator, authInstance, username)


def authCallbackUrl(authenticator):
    '''
    Helper method, so we can get the auth call back url for an authenticator
    '''
    from django.core.urlresolvers import reverse
    return reverse('uds.web.views.authCallback', kwargs={'authName': authenticator.name})


def authInfoUrl(authenticator):
    '''
    Helper method, so we can get the info url for an authenticator
    '''
    from django.core.urlresolvers import reverse
    if isinstance(authenticator, unicode) or isinstance(authenticator, str):
        name = authenticator
    else:
        name = authenticator.name

    return reverse('uds.web.views.authInfo', kwargs={'authName': name})


def webLogin(request, response, user, password):
    '''
    Helper function to, once the user is authenticated, store the information at the user session.
    @return: Always returns True
    '''
    from uds import REST

    if user.id != ROOT_ID:  # If not ROOT user (this user is not inside any authenticator)
        manager_id = user.manager.id
    else:
        manager_id = -1
    user.updateLastAccess()
    request.session.clear()
    request.session[USER_KEY] = user.id
    request.session[PASS_KEY] = CryptoManager.manager().xor(password.encode('utf-8'), request.COOKIES['uds'])
    # Ensures that this user will have access througt REST api if logged in through web interface
    REST.Handler.storeSessionAuthdata(request.session, manager_id, user.name, get_language(), user.is_admin, user.staff_member)
    return True


def webPassword(request):
    '''
    The password is stored at session using a simple scramble algorithm that keeps the password splited at
    session (db) and client browser cookies. This method uses this two values to recompose the user password
    so we can provide it to remote sessions.
    @param request: DJango Request
    @return: Unscrambled user password
    '''
    return CryptoManager.manager().xor(request.session.get(PASS_KEY), request.COOKIES['uds']).decode('utf-8')


def webLogout(request, exit_url=None):
    '''
    Helper function to clear user related data from session. If this method is not used, the session we be cleaned anyway
    by django in regular basis.
    '''
    # Invoke esit for authenticator
    request.session.clear()
    if exit_url is None:
        exit_url = GlobalConfig.LOGIN_URL.get()
    # Try to delete session
    return HttpResponseRedirect(request.build_absolute_uri(exit_url))


def authLogLogin(request, authenticator, userName, java, os, logStr=''):
    '''
    Logs authentication
    '''

    if logStr == '':
        logStr = 'Logged in'

    javaStr = java and 'Java' or 'No Java'
    authLogger.info('|'.join([authenticator.name, userName, javaStr, os['OS'], logStr, request.META['HTTP_USER_AGENT']]))
    level = (logStr == 'Logged in') and log.INFO or log.ERROR
    log.doLog(authenticator, level, 'user {0} has {1} from {2} {3} java and os is {4}'.format(userName, logStr,
          request.ip, java and 'has' or 'has NOT', os['OS']), log.WEB)

    try:
        user = authenticator.users.get(name=userName)
        log.doLog(user, level, '{0} from {1} {2} java and os is {3}'.format(logStr,
                request.ip, java and 'has' or 'has NOT', os['OS']), log.WEB)
    except:
        pass


def authLogLogout(request):
    log.doLog(request.user.manager, log.INFO, 'user {0} has logged out from {1}'.format(request.user.name, request.ip), log.WEB)
    log.doLog(request.user, log.INFO, 'has logged out from {0}'.format(request.ip), log.WEB)
