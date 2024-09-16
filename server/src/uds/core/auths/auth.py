# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import logging
import typing

from functools import wraps
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse,
    HttpRequest,
)
from django.utils.translation import get_language
from django.urls import reverse

from django.utils.translation import ugettext as _

from uds.core import auths
from uds.core.util import log
from uds.core.util import net
from uds.core.util import config
from uds.core.util.config import GlobalConfig
from uds.core.util.stats import events
from uds.core.util.state import State
from uds.core.managers import cryptoManager
from uds.core.auths import Authenticator as AuthenticatorInstance

from uds.models import User, Authenticator

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest, ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)
authLogger = logging.getLogger('authLog')

USER_KEY = 'uk'
PASS_KEY = 'pk'
EXPIRY_KEY = 'ek'
AUTHORIZED_KEY = 'ak'
ROOT_ID = -20091204  # Any negative number will do the trick
UDS_COOKIE_LENGTH = 48

RT = typing.TypeVar('RT')


def getUDSCookie(
    request: HttpRequest,
    response: typing.Optional[HttpResponse] = None,
    force: bool = False,
) -> str:
    """
    Generates a random cookie for uds, used, for example, to encript things
    """
    if 'uds' not in request.COOKIES:
        cookie = cryptoManager().randomString(UDS_COOKIE_LENGTH)
        if response is not None:
            response.set_cookie(
                'uds', cookie, samesite='Lax', httponly=GlobalConfig.ENHANCED_SECURITY.getBool()
            )
        request.COOKIES['uds'] = cookie
    else:
        cookie = request.COOKIES['uds'][:UDS_COOKIE_LENGTH]

    if response and force:
        response.set_cookie('uds', cookie)

    return cookie


def getRootUser() -> User:
    """
    Returns an user not in DB that is ROOT for the platform

    Returns:
        User: [description]
    """
    user = User(
        id=ROOT_ID,
        name=GlobalConfig.SUPER_USER_LOGIN.get(True),
        real_name=_('System Administrator'),
        state=State.ACTIVE,
        staff_member=True,
        is_admin=True,
    )
    user.manager = Authenticator()  # type: ignore
    # Fake overwrite some methods, a bit cheating? maybe? :)
    user.getGroups = lambda: []  # type: ignore
    user.updateLastAccess = lambda: None  # type: ignore
    user.logout = lambda: None  # type: ignore
    return user


# Decorator to make easier protect pages that needs to be logged in
def webLoginRequired(
    admin: typing.Union[bool, typing.Literal['admin']] = False
) -> typing.Callable[[typing.Callable[..., HttpResponse]], typing.Callable[..., HttpResponse]]:
    """Decorator to set protection to access page
    Look for samples at uds.core.web.views
    if admin == True, needs admin or staff
    if admin == 'admin', needs admin

    Args:
        admin (bool, optional): If True, needs admin or staff. Is it's "admin" literal, needs admin . Defaults to False (any user).

    Returns:
        typing.Callable[[typing.Callable[..., HttpResponse]], typing.Callable[..., HttpResponse]]: Decorator

    Note:
        This decorator is used to protect pages that needs to be logged in.
        To protect against ajax calls, use `denyNonAuthenticated` instead
    """

    def decorator(view_func: typing.Callable[..., HttpResponse]) -> typing.Callable[..., HttpResponse]:
        @wraps(view_func)
        def _wrapped_view(request: 'ExtendedHttpRequest', *args, **kwargs) -> HttpResponse:
            """
            Wrapped function for decorator
            """
            # If no user or user authorization is not completed...
            if not request.user or not request.authorized:
                return HttpResponseRedirect(reverse('page.login'))

            if admin in (True, 'admin'):
                if request.user.isStaff() is False or (admin == 'admin' and not request.user.is_admin):
                    return HttpResponseForbidden(_('Forbidden'))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Helper for checking if requests is from trusted source
def isTrustedSource(ip: str) -> bool:
    return net.ipInNetwork(ip, GlobalConfig.TRUSTED_SOURCES.get(True))


# Decorator to protect pages that needs to be accessed from "trusted sites"
def trustedSourceRequired(view_func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    """
    Decorator to set protection to access page
    """

    @wraps(view_func)
    def _wrapped_view(request: 'ExtendedHttpRequest', *args, **kwargs) -> RT:
        """
        Wrapped function for decorator
        """
        try:
            if not isTrustedSource(request.ip):
                return HttpResponseForbidden()  # type: ignore
        except Exception as e:
            logger.warning(
                'Error checking trusted source: "%s" does not seems to be a valid network string. Using Unrestricted access.',
                GlobalConfig.TRUSTED_SOURCES.get(),
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# decorator to deny non authenticated requests
# The difference with webLoginRequired is that this one does not redirect to login page
# it's designed to be used in ajax calls mainly
def denyNonAuthenticated(view_func: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    @wraps(view_func)
    def _wrapped_view(request: 'ExtendedHttpRequest', *args, **kwargs) -> RT:
        if not request.user or not request.authorized:
            return HttpResponseForbidden()  # type: ignore
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def __registerUser(
    authenticator: Authenticator, authInstance: AuthenticatorInstance, username: str
) -> typing.Optional[User]:
    """
    Check if this user already exists on database with this authenticator, if don't, create it with defaults
    This will work correctly with both internal or externals cause we first authenticate the user, if internal and user do not exists in database
    authenticate will return false, if external and return true, will create a reference in database
    """
    from uds.core.util.request import getRequest

    username = authInstance.transformUsername(username)
    logger.debug('Transformed username: %s', username)

    request = getRequest()

    usr = authenticator.getOrCreateUser(username, username)
    usr.real_name = authInstance.getRealName(username)
    usr.save()
    if usr is not None and State.isActive(usr.state):
        # Now we update database groups for this user
        usr.getManager().recreateGroups(usr)
        # And add an login event
        events.addEvent(authenticator, events.ET_LOGIN, username=username, srcip=request.ip)
        events.addEvent(
            authenticator,
            events.ET_PLATFORM,
            platform=request.os['OS'].value[0],
            browser=request.os['Browser'],
            version=request.os['Version'],
        )
        return usr

    return None


def authenticate(
    username: str,
    password: str,
    authenticator: Authenticator,
    useInternalAuthenticate: bool = False,
) -> typing.Optional[User]:
    """
    Given an username, password and authenticator, try to authenticate user
    @param username: username to authenticate
    @param password: password to authenticate this user
    @param authenticator: Authenticator (database object) used to authenticate with provided credentials
    @param useInternalAuthenticate: If True, tries to authenticate user using "internalAuthenticate". If false, it uses "authenticate".
                                    This is so because in some situations we may want to use a "trusted" method (internalAuthenticate is never invoked directly from web)
    @return: None if authentication fails, User object (database object) if authentication is o.k.
    """
    logger.debug('Authenticating user %s with authenticator %s', username, authenticator)

    # If global root auth is enabled && user/password is correct,
    if (
        not useInternalAuthenticate
        and GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.getBool(True)
        and username == GlobalConfig.SUPER_USER_LOGIN.get(True)
        and password == GlobalConfig.SUPER_USER_PASS.get(True)
    ):
        return getRootUser()

    gm = auths.GroupsManager(authenticator)
    authInstance = authenticator.getInstance()
    if useInternalAuthenticate is False:
        res = authInstance.authenticate(username, password, gm)
    else:
        res = authInstance.internalAuthenticate(username, password, gm)

    if res is False:
        return None

    if isinstance(res, str):
        return res  # type: ignore  # note: temporal fix on >= 3.5 for possible redirect on failed login

    logger.debug('Groups manager: %s', gm)

    # If do not have any valid group
    if gm.hasValidGroups() is False:
        logger.info(
            'User %s has been authenticated, but he does not belongs to any UDS known group',
            username,
        )
        return None

    return __registerUser(authenticator, authInstance, username)


def authenticateViaCallback(authenticator: Authenticator, params: typing.Any) -> typing.Optional[User]:
    """
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
    """
    gm = auths.GroupsManager(authenticator)
    authInstance = authenticator.getInstance()
    
    logger.debug('Authenticating user with authenticator %s and params %s', authenticator, params)

    # If there is no callback for this authenticator...
    if authInstance.authCallback is auths.Authenticator.authCallback:
        raise auths.exceptions.InvalidAuthenticatorException()

    username = authInstance.authCallback(params, gm)

    if username is None or username == '' or gm.hasValidGroups() is False:
        raise auths.exceptions.InvalidUserException('User doesn\'t has access to UDS')

    return __registerUser(authenticator, authInstance, username)


def authCallbackUrl(authenticator: Authenticator) -> str:
    """
    Helper method, so we can get the auth call back url for an authenticator
    """
    return reverse('page.auth.callback', kwargs={'authName': authenticator.name})


def authInfoUrl(authenticator: typing.Union[str, bytes, Authenticator]) -> str:
    """
    Helper method, so we can get the info url for an authenticator
    """
    if isinstance(authenticator, str):
        name = authenticator
    elif isinstance(authenticator, bytes):
        name = authenticator.decode('utf8')
    else:
        name = typing.cast('Authenticator', authenticator).name

    return reverse('page.auth.info', kwargs={'authName': name})


def webLogin(
    request: 'ExtendedHttpRequest',
    response: typing.Optional[HttpResponse],
    user: User,
    password: str,
) -> bool:
    """
    Helper function to, once the user is authenticated, store the information at the user session.
    @return: Always returns True
    """
    from uds import REST

    if user.id != ROOT_ID:  # If not ROOT user (this user is not inside any authenticator)
        manager_id = user.manager.id
    else:
        manager_id = -1

    # If for any reason the "uds" cookie is removed, recreated it
    cookie = getUDSCookie(request, response)

    user.updateLastAccess()
    request.authorized = False  # For now, we don't know if the user is authorized until MFA is checked
    # If Enabled zero trust, do not cache credentials
    if GlobalConfig.ENFORCE_ZERO_TRUST.getBool(False):
        password = ''

    request.session[USER_KEY] = user.id
    request.session[PASS_KEY] = cryptoManager().symCrypt(password, cookie)  # Stores "bytes"

    # Ensures that this user will have access through REST api if logged in through web interface
    # Note that REST api will set the session expiry to selected value if user is an administrator
    REST.Handler.storeSessionAuthdata(
        request.session,
        manager_id,
        user.name,
        password,
        get_language() or '',
        request.os['OS'].value[0],
        user.is_admin,
        user.staff_member,
        cookie,
    )
    return True


def webPassword(request: HttpRequest) -> str:
    """
    The password is stored at session using a simple scramble algorithm that keeps the password splited at
    session (db) and client browser cookies. This method uses this two values to recompose the user password
    so we can provide it to remote sessions.
    """
    if hasattr(request, '_cryptedpass') and hasattr(request, '_scrambler'):
        return cryptoManager().symDecrpyt(
            getattr(request, '_cryptedpass'),
            getattr(request, '_scrambler'),
        )
    return cryptoManager().symDecrpyt(
        request.session.get(PASS_KEY, ''), getUDSCookie(request)
    )  # recover as original unicode string


def webLogout(request: 'ExtendedHttpRequest', exit_url: typing.Optional[str] = None) -> HttpResponse:
    """
    Helper function to clear user related data from session. If this method is not used, the session we be cleaned anyway
    by django in regular basis.
    """
    tag = request.session.get('tag', None)
    if tag and config.GlobalConfig.REDIRECT_TO_TAG_ON_LOGOUT.getBool(False):
        exit_page = reverse('page.login.tag', kwargs={'tag': tag})
    else:
        exit_page = reverse('page.login')
    exit_url = exit_url or exit_page
    try:
        if request.user:
            authenticator = request.user.manager.getInstance()
            username = request.user.name
            exit_url = authenticator.logout(username) or exit_url
            if request.user.id != ROOT_ID:
                # Log the event if not root user
                events.addEvent(
                    request.user.manager,
                    events.ET_LOGOUT,
                    username=request.user.name,
                    srcip=request.ip,
                )
        else:  # No user, redirect to /
            return HttpResponseRedirect(exit_page)
    except Exception:
        raise
    finally:
        # Try to delete session
        request.session.flush()
        request.authorized = False

    response = HttpResponseRedirect(exit_url)
    if authenticator:
        authenticator.webLogoutHook(username, request, response)
    return response


def authLogLogin(
    request: 'ExtendedHttpRequest',
    authenticator: Authenticator,
    userName: str,
    logStr: str = '',
) -> None:
    """
    Logs authentication
    """
    if logStr == '':
        logStr = 'Logged in'

    authLogger.info(
        '|'.join(
            [
                authenticator.name,
                userName,
                request.ip,
                request.os['OS'].value[0],
                logStr,
                request.META.get('HTTP_USER_AGENT', 'Undefined'),
            ]
        )
    )
    level = log.INFO if logStr in ('Logged in', 'Federated login') else log.ERROR
    log.doLog(
        authenticator,
        level,
        'user {} has {} from {} where os is {}'.format(userName, logStr, request.ip, request.os['OS'].value[0]),
        log.WEB,
    )

    try:
        user = authenticator.users.get(name=userName)
        log.doLog(
            user,
            level,
            '{} from {} where OS is {}'.format(logStr, request.ip, request.os['OS'].value[0]),
            log.WEB,
        )
    except Exception:
        pass


def authLogLogout(request: 'ExtendedHttpRequest') -> None:
    if request.user:
        log.doLog(
            request.user.manager,
            log.INFO,
            'user {} has logged out from {}'.format(request.user.name, request.ip),
            log.WEB,
        )
        log.doLog(request.user, log.INFO, 'has logged out from {}'.format(request.ip), log.WEB)
