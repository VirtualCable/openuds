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

'''
Provides useful functions for authenticating, used by web interface.


Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import base64
import logging
import typing
import collections.abc
import codecs

from functools import wraps
from django.http import (
    HttpResponseRedirect,
    HttpResponseForbidden,
    HttpResponse,
    HttpRequest,
)
from django.utils.translation import get_language
from django.urls import reverse

from django.utils.translation import gettext as _

from uds.core import auths, types, exceptions, consts
from uds.core.types.requests import ExtendedHttpRequest
from uds.core.util import log
from uds.core.util import net
from uds.core.util import config
from uds.core.util.config import GlobalConfig
from uds.core.util.stats import events
from uds.core.types.states import State
from uds.core.managers.crypto import CryptoManager
from uds.core.auths import Authenticator as AuthenticatorInstance

from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)
authLogger = logging.getLogger('authLog')


RT = typing.TypeVar('RT')


# Local type only
class AuthResult(typing.NamedTuple):
    user: typing.Optional[models.User] = None
    url: typing.Optional[str] = None


def uds_cookie(
    request: HttpRequest,
    response: typing.Optional[HttpResponse] = None,
    force: bool = False,
) -> str:
    """
    Generates a random cookie for uds, used, for example, to encript things
    """
    if 'uds' not in request.COOKIES:
        cookie = CryptoManager().random_string(consts.auth.UDS_COOKIE_LENGTH)
        if response is not None:
            response.set_cookie(
                'uds',
                cookie,
                samesite='Lax',
                httponly=GlobalConfig.ENHANCED_SECURITY.as_bool(),
            )
        request.COOKIES['uds'] = cookie
    else:
        cookie = request.COOKIES['uds'][: consts.auth.UDS_COOKIE_LENGTH]

    if response and force:
        response.set_cookie('uds', cookie)

    return cookie


def root_user() -> models.User:
    """
    Returns an user not in DB that is ROOT for the platform

    Returns:
        User: [description]
    """
    user = models.User(
        id=consts.auth.ROOT_ID,
        name=GlobalConfig.SUPER_USER_LOGIN.get(True),
        real_name=_('System Administrator'),
        state=State.ACTIVE,
        staff_member=True,
        is_admin=True,
    )
    user.manager = models.Authenticator()
    # Fake overwrite some methods, a bit cheating? maybe? :)
    user.get_groups = lambda: []  # type: ignore
    user.update_last_access = lambda: None  # type: ignore
    # Override logout method to do nothing for this user
    user.logout = lambda request: types.auth.SUCCESS_AUTH  # type: ignore
    return user


# Decorator to make easier protect pages that needs to be logged in
def web_login_required(
    admin: typing.Union[bool, typing.Literal['admin']] = False
) -> collections.abc.Callable[
    [collections.abc.Callable[..., HttpResponse]], collections.abc.Callable[..., HttpResponse]
]:
    """Decorator to set protection to access page
    Look for samples at uds.core.web.views
    if admin == True, needs admin or staff
    if admin == 'admin', needs admin

    Args:
        admin (bool, optional): If True, needs admin or staff. Is it's "admin" literal, needs admin . Defaults to False (any user).

    Returns:
        collections.abc.Callable[[collections.abc.Callable[..., HttpResponse]], collections.abc.Callable[..., HttpResponse]]: Decorator

    Note:
        This decorator is used to protect pages that needs to be logged in.
        To protect against ajax calls, use `denyNonAuthenticated` instead
    """

    def decorator(
        view_func: collections.abc.Callable[..., HttpResponse]
    ) -> collections.abc.Callable[..., HttpResponse]:
        @wraps(view_func)
        def _wrapped_view(
            request: 'ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any
        ) -> HttpResponse:
            """
            Wrapped function for decorator
            """
            # If no user or user authorization is not completed...
            if not request.user or not request.authorized:
                return HttpResponseRedirect(reverse('page.login'))

            if admin in (True, 'admin'):
                if request.user.is_staff() is False or (admin == 'admin' and not request.user.is_admin):
                    return HttpResponseForbidden(_('Forbidden'))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Helper for checking if requests is from trusted source
def is_source_trusted(ip: str) -> bool:
    return net.contains(GlobalConfig.TRUSTED_SOURCES.get(True), ip)


# Decorator to protect pages that needs to be accessed from "trusted sites"
def needs_trusted_source(
    view_func: collections.abc.Callable[..., HttpResponse]
) -> collections.abc.Callable[..., HttpResponse]:
    """
    Decorator to set protection to access page
    """

    @wraps(view_func)
    def _wrapped_view(request: 'ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any) -> HttpResponse:
        """
        Wrapped function for decorator
        """
        try:
            if not is_source_trusted(request.ip):
                return HttpResponseForbidden()
        except Exception:
            logger.warning(
                'Error checking trusted source: "%s" does not seems to be a valid network string. Using Unrestricted access.',
                GlobalConfig.TRUSTED_SOURCES.get(),
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# decorator to deny non authenticated requests
# The difference with web_login_required is that this one does not redirect to login page
# it's designed to be used in ajax calls mainly
def deny_non_authenticated(view_func: collections.abc.Callable[..., RT]) -> collections.abc.Callable[..., RT]:
    @wraps(view_func)
    def _wrapped_view(request: 'ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any) -> RT:
        if not request.user or not request.authorized:
            return HttpResponseForbidden()  # type: ignore
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def register_user(
    authenticator: models.Authenticator,
    authInstance: AuthenticatorInstance,
    username: str,
    request: 'ExtendedHttpRequest',
) -> AuthResult:
    """
    Check if this user already exists on database with this authenticator, if don't, create it with defaults
    This will work correctly with both internal or externals cause we first authenticate the user, if internal and user do not exists in database
    authenticate will return false, if external and return true, will create a reference in database
    """
    username = authInstance.transformed_username(username, request)
    logger.debug('Transformed username: %s', username)

    usr = authenticator.get_or_create_user(username, username)
    usr.real_name = authInstance.get_real_name(username)
    usr.save()
    if usr is not None and State.from_str(usr.state).is_active():
        # Now we update database groups for this user
        usr.get_manager().recreate_groups(usr)
        # And add an login event
        events.add_event(authenticator, events.types.stats.EventType.LOGIN, username=username, srcip=request.ip)
        events.add_event(
            authenticator,
            events.types.stats.EventType.PLATFORM,
            platform=request.os.os.name,
            browser=request.os.browser,
            version=request.os.version,
        )
        return AuthResult(user=usr)

    return AuthResult()


def authenticate(
    username: str,
    password: str,
    authenticator: models.Authenticator,
    request: 'ExtendedHttpRequest',
    useInternalAuthenticate: bool = False,
) -> AuthResult:
    """
    Given an username, password and authenticator, try to authenticate user
    @param username: username to authenticate
    @param password: password to authenticate this user
    @param authenticator: Authenticator (database object) used to authenticate with provided credentials
    @param request: Request object
    @param useInternalAuthenticate: If True, tries to authenticate user using "internalAuthenticate". If false, it uses "authenticate".
                                    This is so because in some situations we may want to use a "trusted" method (internalAuthenticate is never invoked directly from web)
    @return:
            An AuthResult indicating:
            user if success in logging in field user or None if not
            url if not success in logging in field url so instead of error UDS will redirect to this url


    """
    logger.debug('Authenticating user %s with authenticator %s', username, authenticator)

    # If global root auth is enabled && user/password is correct,
    if (
        not useInternalAuthenticate
        and GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.as_bool(True)
        and username == GlobalConfig.SUPER_USER_LOGIN.get(True)
        and CryptoManager().check_hash(password, GlobalConfig.SUPER_USER_PASS.get(True))
    ):
        return AuthResult(user=root_user())

    gm = auths.GroupsManager(authenticator)
    authInstance = authenticator.get_instance()
    if useInternalAuthenticate is False:
        res = authInstance.authenticate(username, password, gm, request)
    else:
        res = authInstance.internal_authenticate(username, password, gm, request)

    if res.success == types.auth.AuthenticationState.FAIL:
        logger.debug('Authentication failed')
        # Maybe it's an redirection on auth failed?
        return AuthResult()

    if res.success == types.auth.AuthenticationState.REDIRECT:
        return AuthResult(url=res.url)

    logger.debug('Groups manager: %s', gm)

    # If do not have any valid group
    if gm.has_valid_groups() is False:
        logger.info(
            'User %s has been authenticated, but he does not belongs to any UDS known group',
            username,
        )
        return AuthResult()

    return register_user(authenticator, authInstance, username, request)


def authenticate_via_callback(
    authenticator: models.Authenticator,
    params: 'types.auth.AuthCallbackParams',
    request: 'ExtendedHttpRequestWithUser',
) -> AuthResult:
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
    auth_instance = authenticator.get_instance()

    # If there is no callback for this authenticator...
    if auth_instance.auth_callback is auths.Authenticator.auth_callback:  # type: ignore   # mypy thins it's a comparison overlap
        raise exceptions.auth.InvalidAuthenticatorException()

    result = auth_instance.auth_callback(params, gm, request)
    if result.success == types.auth.AuthenticationState.FAIL or (
        result.success == types.auth.AuthenticationState.SUCCESS and not gm.has_valid_groups()
    ):
        raise exceptions.auth.InvalidUserException('User doesn\'t has access to UDS')

    if result.success == types.auth.AuthenticationState.REDIRECT:
        return AuthResult(url=result.url)

    if result.username:
        return register_user(authenticator, auth_instance, result.username or '', request)
    else:
        logger.warning('Authenticator %s returned empty username', authenticator.name)

    raise exceptions.auth.InvalidUserException('User doesn\'t has access to UDS')


def authenticate_callback_url(authenticator: models.Authenticator) -> str:
    """
    Helper method, so we can get the auth call back url for an authenticator
    """
    return reverse('page.auth.callback', kwargs={'authenticator_name': authenticator.small_name})


def authenticate_info_url(authenticator: typing.Union[str, bytes, models.Authenticator]) -> str:
    """
    Helper method, so we can get the info url for an authenticator
    """
    if isinstance(authenticator, str):
        name = authenticator
    elif isinstance(authenticator, bytes):
        name = authenticator.decode('utf8')
    elif isinstance(authenticator, models.Authenticator):
        name = authenticator.small_name
    else:
        raise ValueError('Invalid authenticator type')

    return reverse('page.auth.info', kwargs={'authenticator_name': name})


def web_login(
    request: 'ExtendedHttpRequest',
    response: typing.Optional[HttpResponse],
    user: models.User,
    password: str,
) -> bool:
    """
    Helper function to, once the user is authenticated, store the information at the user session.
    @return: Always returns True
    """
    from uds import (  # pylint: disable=import-outside-toplevel  # to avoid circular imports
        REST,
    )

    if user.id != consts.auth.ROOT_ID:  # If not ROOT user (this user is not inside any authenticator)
        manager_id = user.manager.id
    else:
        manager_id = -1

    # If for any reason the "uds" cookie is removed, recreated it
    cookie = uds_cookie(request, response)

    user.update_last_access()
    request.authorized = False  # For now, we don't know if the user is authorized until MFA is checked
    # Store request ip in session
    request.session[consts.auth.SESSION_IP_KEY] = request.ip
    # If Enabled zero trust, do not cache credentials
    if GlobalConfig.ENFORCE_ZERO_TRUST.as_bool(False):
        password = ''  # nosec: clear password if zero trust is enabled

    request.session[consts.auth.SESSION_USER_KEY] = user.id
    request.session[consts.auth.SESSION_PASS_KEY] = codecs.encode(
        CryptoManager().symmetric_encrypt(password, cookie), "base64"
    ).decode()  # as str

    # Ensures that this user will have access through REST api if logged in through web interface
    # Note that REST api will set the session expiry to selected value if user is an administrator
    REST.Handler.set_rest_auth(
        request.session,
        manager_id,
        user.name,
        password,
        get_language() or '',
        request.os.os.name,
        user.is_admin,
        user.staff_member,
        cookie,
    )
    return True


def web_password(request: HttpRequest) -> str:
    """
    The password is stored at session using a simple scramble algorithm that keeps the password splited at
    session (db) and client browser cookies. This method uses this two values to recompose the user password
    so we can provide it to remote sessions.
    """
    if hasattr(request, '_cryptedpass') and hasattr(request, '_scrambler'):
        return CryptoManager.manager().symmetric_decrypt(
            getattr(request, '_cryptedpass'),
            getattr(request, '_scrambler'),
        )
    passkey = base64.b64decode(request.session.get(consts.auth.SESSION_PASS_KEY, ''))
    return CryptoManager().symmetric_decrypt(passkey, uds_cookie(request))  # recover as original unicode string


def web_logout(request: 'ExtendedHttpRequest', exit_url: typing.Optional[str] = None) -> HttpResponse:
    """
    Helper function to clear user related data from session. If this method is not used, the session we be cleaned anyway
    by django in regular basis.
    """
    tag = request.session.get('tag', None)
    if tag and config.GlobalConfig.REDIRECT_TO_TAG_ON_LOGOUT.as_bool(False):
        exit_page = reverse('page.login.tag', kwargs={'tag': tag})
    else:
        exit_page = reverse('page.login')
    exit_url = exit_url or exit_page
    try:
        if request.user:
            authenticator = request.user.manager.get_instance()
            username = request.user.name
            logout = authenticator.logout(request, username)
            if logout and logout.success == types.auth.AuthenticationState.REDIRECT:
                exit_url = logout.url or exit_url
            if request.user.id != consts.auth.ROOT_ID:
                # Log the event if not root user
                events.add_event(
                    request.user.manager,
                    events.types.stats.EventType.LOGOUT,
                    username=request.user.name,
                    srcip=request.ip,
                )
        else:  # No user, redirect to /
            return HttpResponseRedirect(exit_page)
    finally:
        # Try to delete session
        request.session.flush()
        request.authorized = False

    response = HttpResponseRedirect(exit_url)
    if authenticator:
        authenticator.hook_web_logout(username, request, response)
    return response


def log_login(
    request: 'ExtendedHttpRequest',
    authenticator: models.Authenticator,
    userName: str,
    log_string: str = '',
) -> None:
    """
    Logs authentication
    """
    if log_string == '':
        log_string = 'Logged in'

    authLogger.info(
        '|'.join(
            [
                authenticator.name,
                userName,
                request.ip,
                request.os.os.name,
                log_string,
                request.META.get('HTTP_USER_AGENT', 'Undefined'),
            ]
        )
    )
    level = log.LogLevel.INFO if log_string == 'Logged in' else log.LogLevel.ERROR
    log.log(
        authenticator,
        level,
        f'user {userName} has {log_string} from {request.ip} where os is {request.os.os.name}',
        log.LogSource.WEB,
    )

    try:
        # Root user is not on any authenticator, so we cannot attach log to an db user
        user = authenticator.users.get(name=userName)
        log.log(
            user,
            level,
            f'{log_string} from {request.ip} where OS is {request.os.os.name}',
            log.LogSource.WEB,
        )
    except Exception:  # nosec: root user is not on any authenticator, will fail with an exception we can ingore
        logger.info('Root %s from %s where OS is %s', log_string, request.ip, request.os.os.name)


def log_logout(request: 'ExtendedHttpRequest') -> None:
    if request.user:
        if request.user.manager.id is not None:
            log.log(
                request.user.manager,
                log.LogLevel.INFO,
                f'user {request.user.name} has logged out from {request.ip}',
                log.LogSource.WEB,
            )
            log.log(request.user, log.LogLevel.INFO, f'has logged out from {request.ip}', log.LogSource.WEB)
        else:
            logger.info('Root has logged out from %s', request.ip)
