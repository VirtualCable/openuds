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
import codecs
import collections.abc
import logging
import typing
from functools import wraps

from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from uds import models
from uds.core import auths, consts, exceptions, types
from uds.core.auths import Authenticator as AuthenticatorInstance, callbacks
from uds.core.util import config, log, net
from uds.core.util.stats import events
from uds.core.managers.crypto import CryptoManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)
auth_logger = logging.getLogger('authLog')


RT = typing.TypeVar('RT')


# Local type only
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
                httponly=config.GlobalConfig.ENHANCED_SECURITY.as_bool(),
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
        name=config.GlobalConfig.SUPER_USER_LOGIN.get(True),
        real_name=_('System Administrator'),
        state=types.states.State.ACTIVE,
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
def weblogin_required(
    role: typing.Optional[consts.Roles] = None,
) -> collections.abc.Callable[
    [collections.abc.Callable[..., HttpResponse]], collections.abc.Callable[..., HttpResponse]
]:
    """Decorator to set protection to access page
    
    Args:
        role (str, optional): If set, needs this role. Defaults to None.

    Returns:
        collections.abc.Callable[[collections.abc.Callable[..., HttpResponse]], collections.abc.Callable[..., HttpResponse]]: Decorator

    Note:
        This decorator is used to protect pages that needs to be logged in.
        To protect against ajax calls, use `denyNonAuthenticated` instead
        Roles as "inclusive", that is, if you set role to USER, it will allow all users that are not anonymous. (USER, STAFF, ADMIN)
    """

    def decorator(
        view_func: collections.abc.Callable[..., HttpResponse]
    ) -> collections.abc.Callable[..., HttpResponse]:
        @wraps(view_func)
        def _wrapped_view(
            request: 'types.requests.ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any
        ) -> HttpResponse:
            """
            Wrapped function for decorator
            """
            # If no user or user authorization is not completed...
            if not request.user or not request.authorized:
                return weblogout(request)

            if role in (consts.Roles.ADMIN, consts.Roles.STAFF):
                if request.user.is_staff() is False or (role == consts.Roles.ADMIN and not request.user.is_admin):
                    return HttpResponseForbidden(_('Forbidden'))

            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


# Helper for checking if requests is from trusted source
def is_trusted_source(ip: str) -> bool:
    return net.contains(config.GlobalConfig.TRUSTED_SOURCES.get(True), ip)


def is_trusted_ip_forwarder(ip: str) -> bool:
    return net.contains(config.GlobalConfig.ALLOWED_IP_FORWARDERS.get(True), ip)


# Decorator to protect pages that needs to be accessed from "trusted sites"
def needs_trusted_source(
    view_func: collections.abc.Callable[..., HttpResponse]
) -> collections.abc.Callable[..., HttpResponse]:
    """
    Decorator to set protection to access page
    """

    @wraps(view_func)
    def _wrapped_view(
        request: 'types.requests.ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any
    ) -> HttpResponse:
        """
        Wrapped function for decorator
        """
        try:
            if not is_trusted_source(request.ip):
                return HttpResponseForbidden()
        except Exception:
            logger.warning(
                'Error checking trusted source: "%s" does not seems to be a valid network string. Using Unrestricted access.',
                config.GlobalConfig.TRUSTED_SOURCES.get(),
            )
        return view_func(request, *args, **kwargs)

    return _wrapped_view


# decorator to deny non authenticated requests
# The difference with weblogin_required is that this one does not redirect to login page
# it's designed to be used in ajax calls mainly
def deny_non_authenticated(view_func: collections.abc.Callable[..., RT]) -> collections.abc.Callable[..., RT]:
    @wraps(view_func)
    def _wrapped_view(
        request: 'types.requests.ExtendedHttpRequest', *args: typing.Any, **kwargs: typing.Any
    ) -> RT:
        if not request.user or not request.authorized:
            return HttpResponseForbidden()  # type: ignore
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def register_user(
    authenticator: models.Authenticator,
    auth_instance: AuthenticatorInstance,
    username: str,
    request: 'types.requests.ExtendedHttpRequest',
    skip_callbacks: bool = False,
) -> types.auth.LoginResult:
    """
    Check if this user already exists on database with this authenticator, if don't, create it with defaults
    This will work correctly with both internal or externals cause we first authenticate the user, if internal and user do not exists in database
    authenticate will return false, if external and return true, will create a reference in database
    """
    username = auth_instance.transformed_username(username, request)
    logger.debug('Transformed username: %s', username)

    usr = authenticator.get_or_create_user(username, username)
    usr.real_name = auth_instance.get_real_name(username)
    usr.save()
    if usr and types.states.State.from_str(usr.state).is_active():
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
        if not skip_callbacks:
            callbacks.weblogin(usr)

        return types.auth.LoginResult(user=usr)

    return types.auth.LoginResult()


def authenticate(
    username: str,
    password: str,
    authenticator: models.Authenticator,
    request: 'types.requests.ExtendedHttpRequest',
    skip_callbacks: bool = False,
) -> types.auth.LoginResult:
    """
    Authenticate user with provided credentials

    Args:
        username (str): username to authenticate
        password (str): password to authenticate this user
        authenticator (models.Authenticator): Authenticator (database object) used to authenticate with provided credentials
        request (ExtendedHttpRequestWithUser): Request object
        skip_callbacks (bool, optional): Skip callbacks. Defaults to False.

    """
    logger.debug('Authenticating user %s with authenticator %s', username, authenticator)

    # If global root auth is enabled && user/password is correct,
    # Note: From now onwards, root "we user" can only login from a trusted source
    if (
        config.GlobalConfig.SUPER_USER_ALLOW_WEBACCESS.as_bool(True)
        and is_trusted_source(request.ip)
        and username == config.GlobalConfig.SUPER_USER_LOGIN.get(True)
        and CryptoManager.manager().check_hash(password, config.GlobalConfig.SUPER_USER_PASS.get(True))
    ):
        return types.auth.LoginResult(user=root_user())

    gm = auths.GroupsManager(authenticator)
    auth_instance = authenticator.get_instance()

    if auth_instance.is_ip_allowed(request=request) is False:
        log_login(
            request,
            authenticator,
            username,
            'Access tried from an unallowed source',
            as_error=True,
        )
        return types.auth.LoginResult(errstr=_('Access tried from an unallowed source'))

    res = auth_instance.authenticate(username, password, gm, request)

    if res.success == types.auth.AuthenticationState.FAIL:
        logger.debug('Authentication failed')
        # Maybe it's an redirection on auth failed?
        return types.auth.LoginResult()

    if res.success == types.auth.AuthenticationState.REDIRECT:
        return types.auth.LoginResult(url=res.url)

    logger.debug('Groups manager: %s', gm)

    # If do not have any valid group
    if gm.has_valid_groups() is False:
        logger.info(
            'User %s has been authenticated, but he does not belongs to any UDS known group',
            username,
        )
        return types.auth.LoginResult()

    return register_user(authenticator, auth_instance, username, request)


def authenticate_via_callback(
    authenticator: models.Authenticator,
    params: 'types.auth.AuthCallbackParams',
    request: 'ExtendedHttpRequestWithUser',
) -> types.auth.LoginResult:
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
       * Update user group membership using Authenticator get_groups, so, in your
         callbacks, remember to store (using provided environment storage, for example)
         the groups of this user so your get_groups will work correctly.
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
        return types.auth.LoginResult(url=result.url)

    if not result.username:
        logger.warning('Authenticator %s returned empty username', authenticator.name)
        raise exceptions.auth.InvalidUserException('User doesn\'t has access to UDS')

    return register_user(authenticator, auth_instance, result.username, request)


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
    else:
        name = authenticator.small_name

    return reverse('page.auth.info', kwargs={'authenticator_name': name})


def weblogin(
    request: 'types.requests.ExtendedHttpRequest',
    response: typing.Optional[HttpResponse],
    user: models.User,
    password: str,
) -> bool:
    """
    Helper function to, once the user is authenticated, store the information at the user session.
    @return: Always returns True
    """
    from uds import REST  # pylint: disable=import-outside-toplevel  # to avoid circular imports

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
    if config.GlobalConfig.ENFORCE_ZERO_TRUST.as_bool(False):
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


def get_webpassword(request: HttpRequest) -> str:
    """
    The password is stored at session using a simple scramble algorithm that keeps the password splited at
    session (db) and client browser cookies. This method uses this two values to recompose the user password
    so we can provide it to remote sessions. (this way, the password is never completely stored at any side)
    """
    if hasattr(request, '_cryptedpass') and hasattr(request, '_scrambler'):
        return CryptoManager.manager().symmetric_decrypt(
            getattr(request, '_cryptedpass'),
            getattr(request, '_scrambler'),
        )
    passkey = base64.b64decode(request.session.get(consts.auth.SESSION_PASS_KEY, ''))
    return CryptoManager().symmetric_decrypt(passkey, uds_cookie(request))  # recover as original unicode string


def weblogout(
    request: 'types.requests.ExtendedHttpRequest',
    exit_url: typing.Optional[str] = None,
) -> HttpResponse:
    """
    Helper function to clear user related data from session. If this method is not used, the session we be cleaned anyway
    by django in regular basis.
    """
    tag = request.session.pop('tag', None)
    if tag and config.GlobalConfig.REDIRECT_TO_TAG_ON_LOGOUT.as_bool(False):
        exit_page = reverse(types.auth.AuthenticationInternalUrl.LOGIN_LABEL, kwargs={'tag': tag})
    else:
        # remove, if exists, tag from session
        exit_page = reverse(types.auth.AuthenticationInternalUrl.LOGIN)

    response = HttpResponseRedirect(exit_url or exit_page)
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
            authenticator.hook_web_logout(username, request, response)
    finally:
        # Try to delete session
        request.session.flush()
        request.authorized = False

    return response


def log_login(
    request: 'types.requests.ExtendedHttpRequest',
    authenticator: models.Authenticator,
    username: str,
    log_string: str = '',
    as_error: bool = False,
) -> None:
    """
    Logs authentication
    """
    if log_string == '':
        log_string = 'Logged in'

    log_level = types.log.LogLevel.ERROR if as_error else types.log.LogLevel.INFO

    auth_logger.info(
        '|'.join(
            [
                authenticator.name,
                username,
                request.ip,
                request.os.os.name,
                log_string,
                request.META.get('HTTP_USER_AGENT', 'Undefined'),
            ]
        )
    )
    log.log(
        authenticator,
        log_level,
        f'user {username} has {log_string} from {request.ip} where os is {request.os.os.name}',
        types.log.LogSource.WEB,
    )

    try:
        # Root user is not on any authenticator, so we cannot attach log to an db user
        user = authenticator.users.get(name=username)
        log.log(
            user,
            log_level,
            f'{log_string} from {request.ip} where OS is {request.os.os.name}',
            types.log.LogSource.WEB,
        )
    except Exception:  # nosec: root user is not on any authenticator, will fail with an exception we can ingore
        logger.info('Root %s from %s where OS is %s', log_string, request.ip, request.os.os.name)


def log_logout(request: 'types.requests.ExtendedHttpRequest') -> None:
    if request.user:
        if request.user.manager.id:
            log.log(
                request.user.manager,
                types.log.LogLevel.INFO,
                f'user {request.user.name} has logged out from {request.ip}',
                types.log.LogSource.WEB,
            )
            log.log(
                request.user,
                types.log.LogLevel.INFO,
                f'has logged out from {request.ip}',
                types.log.LogSource.WEB,
            )
        else:
            logger.info('Root has logged out from %s', request.ip)
