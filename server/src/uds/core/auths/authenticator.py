# pylint: disable=unused-argument  # this has a lot of "default" methods, so we need to ignore unused arguments most of the time

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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

"""
Base module for all authenticators

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core.module import Module
from uds.core import consts, types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.http import (
        HttpRequest,
        HttpResponse,
    )
    from uds import models
    from uds.core.types.requests import ExtendedHttpRequest
    from uds.core.environment import Environment
    from uds.core import types
    from .groups_manager import GroupsManager


logger = logging.getLogger(__name__)


class Authenticator(Module):
    """
    This class represents the base interface to implement authenticators.

    An authenticator is responsible for managing user and groups of a kind
    inside UDS. As so, it must provide a number of method and mechanics to
    allow UDS to manage users and groups using that kind of authenticator.

    Some samples of authenticators are LDAP, Internal Database, SAML, CAS, ...

    As always, if you override __init__, do not forget to invoke base __init__ as this::

       super(self.__class__, self).__init__(self, environment, values, uuid)

    This is a MUST, so internal structured gets filled correctly, so don't forget it!.

    The preferred method of doing initialization is to provide the :py:meth:`.initialize`,
    and do not override __init__ method. This (initialize) will be invoked after
    all internal initialization.

    There are basically two kind of authenticators, that are "Externals" and
    "Internals".

    Internal authenticators are those where and administrator has created manually
    the user at admin interface. The users are not created from an external source,
    so if an user do not exist at UDS database, it will not be valid.
    In other words, if you have an authenticator where you must create users,
    you can modify them, you must assign passwords manually, and group membership
    also must be assigned manually, the authenticator is not an external_source.

    As you can notice, almost avery authenticator except internal db will be
    external source, so, by default, attribute that indicates that is an external
    source is set to True.


    In fact, internal source authenticator is intended to allow UDS to identify
    if the users come from internal DB (just the case of local authenticator),
    or the users come from other sources. Also, this allos UDS to know when to
    "update" group membership information for an user whenever it logs in.

    External authenticator are in fact all authenticators except local database,
    so we have defined external_source as True by default, that will be most
    cases.

    :note: All attributes that are "_" here means that they will be
           translated when provided to administration interface, so remember
           to mark them in your own authenticators as "_" using
           gettext_noop. We have aliased it here to "_" so it's
           easier to understand.
    """

    # : Name of type, used at administration interface to identify this
    # : authenticator (i.e. LDAP, SAML, ...)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_name: typing.ClassVar[str] = _('Base Authenticator')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    type_type: typing.ClassVar[str] = 'Authenticator'

    # : Description shown at administration level for this authenticator.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_description: typing.ClassVar[str] = _('Base Authenticator')

    # : Icon file, used to represent this authenticator at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    icon_file: typing.ClassVar[str] = 'auth.png'

    # : Mark this authenticator as that the users comes from outside the UDS
    # : database, that are most authenticator (except Internal DB)
    # : So, external_source means that "user is kept at database only"
    external_source: typing.ClassVar[bool] = True
    
    # : Mark this authenticator as mfa data enabled (so mfa field appears on the user)
    mfa_data_enabled: typing.ClassVar[bool] = False

    # : If we need to enter the password for this user when creating a new
    # : user at administration interface. Used basically by internal authenticator.
    needs_password: typing.ClassVar[bool] = False

    # : Label for username field, shown at administration interface user form.
    label_username: typing.ClassVar[str] = _('User name')

    # : Label for group field, shown at administration interface user form.
    label_groupname: typing.ClassVar[str] = _('Group name')

    # : Label for password field, , shown at administration interface user form.
    # : Not needed for external authenticators (where credentials are stored with
    # : an already existing user.
    label_password: typing.ClassVar[str] = _('Password')

    # : If this authenticators casues a temporal block of an user on repeated login failures
    block_user_on_failures: typing.ClassVar[bool] = True

    from .user import User  # pylint: disable=import-outside-toplevel
    from .group import Group  # pylint: disable=import-outside-toplevel

    # : The type of user provided, normally standard user will be enough.
    # : This is here so if we need it in some case, we can write our own
    # : user class
    user_type: typing.ClassVar[type[User]] = User

    # : The type of group provided, normally standard group will be enough
    # : This is here so if we need it in some case, we can write our own
    # : group class
    group_type: typing.ClassVar[type[Group]] = Group

    _db_obj: typing.Optional['models.Authenticator'] = None  # Cached dbAuth object

    def __init__(
        self,
        environment: 'Environment',
        values: types.core.ValuesType = None,
        uuid: typing.Optional[str] = None,
    ):
        """
        Instantiathes the authenticator.

        Args:
            environment: Environment for the authenticator
            values: Values passed to element
            uuid: UUID of the authenticator on database, if any.

        Notes:
            Values is None if "unmarshalling" from DB, and is not None if
            we are creating the authenticator from administration interface.
            (Note that other origins can have values, but these are the main ones)

            Same applies to uuid, that will be None if we are creating the authenticator.
        """
        super().__init__(environment, values, uuid=uuid)
        self.initialize(values)

    def initialize(self, values: types.core.ValuesType) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """

    def db_obj(self) -> 'models.Authenticator':
        """
        Helper method to access the Authenticator database object
        """
        from uds.models import Authenticator  # pylint: disable=import-outside-toplevel

        if self._db_obj is None:
            if not self.get_uuid():
                return Authenticator.null()
            # get uuid case insensitive
            self._db_obj = Authenticator.objects.get(uuid__iexact=self.get_uuid())
        return self._db_obj

    def recreate_groups(self, user: 'models.User') -> None:
        """
        Helper method, not needed to be overriden.
        It simply checks if the source is external and if so, recreates
        the user groups for storing them at database.

        user param is a database user object
        """
        from uds.core.auths.groups_manager import (  # pylint: disable=import-outside-toplevel
            GroupsManager,
        )

        if self.external_source:
            groups_manager = GroupsManager(self.db_obj())
            self.get_groups(user.name, groups_manager)
            # cast for typechecking. user.groups is a "simmmilar to a QuerySet", but it's not a QuerySet, so "set" is not there
            user.groups.set([g.db_obj() for g in groups_manager.enumerate_valid_groups()])

    def callback_url(self) -> str:
        """
        Helper method to return callback url for self (authenticator).

        This method will allow us to know where to do redirection in case
        we need to use callback for authentication
        """
        from .auth import authenticate_callback_url  # pylint: disable=import-outside-toplevel

        return authenticate_callback_url(self.db_obj())

    def info_url(self) -> str:
        """
        Helper method to return info url for this authenticator
        """
        from .auth import authenticate_info_url  # pylint: disable=import-outside-toplevel

        return authenticate_info_url(self.db_obj())

    @classmethod
    def is_custom(cls) -> bool:
        """
        Helper to query if a class is custom (implements get_javascript method)

        Returns:
            True if the class has a custom authentication method (and in consequence, a custom javascript)
        """
        return cls.get_javascript is not Authenticator.get_javascript

    @classmethod
    def can_check_user_password(cls) -> bool:
        """
        Helper method to query if a class can do a login using credentials
        """
        return cls.authenticate is not Authenticator.authenticate

    def search_users(self, pattern: str) -> collections.abc.Iterable[types.auth.SearchResultItem]:
        """
        If you provide this method, the user will be allowed to search users,
        that is, the search button at administration interface, at user form,
        will be enabled.

        Returns an array of users that match the supplied pattern
        If none found, returns empty array.

        Must return is an array of dictionaries that must contains 'id' and 'name'
        example: [ {'id': 'user1', 'name': 'Nombre 1'} ]

        Args:
            pattern: Pattern to search for (simple pattern, string)

        Returns
            a list of found users for the pattern specified
        """
        return []

    def search_groups(self, pattern: str) -> collections.abc.Iterable[types.auth.SearchResultItem]:
        """
        Returns an array of groups that match the supplied pattern
        If none found, returns empty array. Items returned are BaseGroups (or derived)
        If you override this method, the admin interface will allow the use of
        "search" at group form. If not overriden, the search will not be allowed.

        Must return array of dictionaries that must contains 'id' and 'name'
        example: [ {'id': 'user1', 'name': 'Nombre 1'} ]

        Default implementation returns empty array, but is never used because if
        not overriden, search of groups will not be allowed.
        """
        return []

    def mfa_identifier(self, username: str) -> str:
        """
        If this method is provided by an authenticator, the user will be allowed to enter a MFA code
        You must return the value used by a MFA provider to identify the user (i.e. email, phone number, etc)
        If not provided, or the return value is '', the user will be allowed to access UDS without MFA
        only if the mfa itself allows empty mfa_identifier. (look at mfa base, allow_login_without_identifier)

        Note: Field capture will be responsible of provider. Put it on MFA tab of user form.
              Take into consideration that mfa_identifier will never be invoked if the user has not been
              previously authenticated. (that is, authenticate method has already been called)
              So, you can store the mfa_identifier at authenticate method, and return it here for example.
        """
        return ''

    @classmethod
    def provides_mfa(cls: typing.Type['Authenticator']) -> bool:
        """
        Returns if this authenticator provides a MFA identifier
        """
        return cls.mfa_identifier is not Authenticator.mfa_identifier

    def authenticate(
        self,
        username: str,
        credentials: str,
        groups_manager: 'GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """
        This method must be overriden, and is responsible for authenticating
        users.

        We can have to different situations here:

           * The authenticator is external source, what means that users may
             be unknown to system before callig this
           * The authenticator isn't external source, what means that users have
             been manually added to system and are known before this call.
             This will only happen at Internal DB Authenticator.

        We receive the username, the credentials used (normally password, but can
        be a public key or something related to pk) and a group manager.

        The group manager is responsible for letting know the authenticator which
        groups we currently has active.

        Args:
            username: User name to authenticate
            credentials: Credentials for this user, (password, pki, or whatever needs to be used). (string)
            groups_manager: Group manager to modify with groups to which this users belongs to.
            request: HttpRequest object

        Returns:
            An authentication result indicating:
                * success:  AuthenticationState.SUCESS if authentication is valid
                            AuthenticationState.FAIL if authentication is invalid
                * username: Username of the user, if success is True
                * url: Url to redirect to, if success is AuthenticationState.REDIRECT

        See uds.core.auths.groups_manager

        Note:
            This method must check not only that the user has valid credentials, but also
            check the valid groups from groupsmanager.
            If this method returns FAIL, of method get_valid_groups of the groups_manager
            passed into this method has no elements, the user will be considered invalid.
            So remember to check validity of groups this user belongs to (inside the authenticator,
            not inside UDS) using groups_mnager.validate(group or groups) to which this users belongs to).

            This is done in this way, because UDS has only a subset of groups for this user, and
            we let the authenticator decide inside wich groups of UDS this users is included.
        """
        return types.auth.FAILED_AUTH

    def is_ip_allowed(self, request: 'types.requests.ExtendedHttpRequest') -> bool:
        """
        Used by the login interface to determine if the authenticator is visible on the login page.
        """
        # Maybe "internal for root", if this is the case, it is valid for all ips
        if not self.db_obj().id:
            return True
        return self.db_obj().state != consts.auth.DISABLED and self.db_obj().is_ip_allowed(request.ip)

    def transformed_username(
        self,
        username: str,
        request: 'types.requests.ExtendedHttpRequest',
    ) -> str:
        """
        On login, this method get called so we can "transform" provided user name.

        Args:
            username: Username to transform

        Returns
            Transformed user name

        :note: You don't need to implement this method if your authenticator (as most authenticators does), does not
               transforms username.
        """
        return username

    def logout(
        self,
        request: 'types.requests.ExtendedHttpRequest',
        username: str,
    ) -> types.auth.AuthenticationResult:
        """
        Invoked whenever an user logs out.

        Notice that authenticators that provides get_javascript method are considered "custom", and
        these authenticators will never be used to allow an user to access administration interface
        (they will be filtered out)

        By default, this method does nothing.

        Args:
            request: HttpRequest object
            username: Name of the user that logged out

        Returns:
                An authentication result indicating:
                  * success on logout
                  * Url to redirect on logout

        :note: This method will be invoked also for administration log out (it it's done), but return
               result will be passed to administration interface, that will invoke the URL but nothing
               will be shown to the user.
               Also, notice that this method will only be invoked "implicity", this means that will be
               invoked if user requests "log out", but maybe it will never be invoked.

        """
        return types.auth.SUCCESS_AUTH

    def hook_web_logout(
        self,
        username: str,
        request: 'HttpRequest',
        response: 'HttpResponse',
    ) -> None:
        '''
        Invoked on web logout of an user
        Args:

            username: Name of the user being logged out of the web
            request: Django request
            response: Django response

        Returns:
            Nothing

        :note: This method will be invoked whenever the web_logout is requested. It receives request & response so auth cna
               make changes (for example, on cookies) to it.

        '''
        return

    def get_for_auth(self, username: str) -> str:
        """
        Process the username for this authenticator and returns it.
        This transformation is used for transports only, not for transforming
        anything at login time. Transports that will need the username, will invoke
        this method.
        For example, an authenticator can add '@domain' so transport use the complete
        'user@domain' instead of 'user'.

        Right now, all authenticators keep this value "as is", i mean, it simply
        returns the unprocessed username
        """
        return username

    def get_groups(self, username: str, groups_manager: 'GroupsManager') -> None:
        """
        Looks for the real groups to which the specified user belongs.

        You MUST override this method, UDS will call it whenever it needs to refresh an user group membership.

        The expected behavior of this method is to mark valid groups in the :py:class:`uds.core.auths.groups_manager` provided, normally
        calling its :py:meth:`uds.core.auths.groups_manager.validate` method with groups names provided by the authenticator itself
        (for example, LDAP, AD, ...)
        """
        raise NotImplementedError

    def get_javascript(self, request: 'ExtendedHttpRequest') -> typing.Optional[str]:
        """
        If you override this method, and returns something different of None,
        UDS will consider your authenticator as "Owner draw", that is, that it
        will not use the standard form for user authentication.

        Args:
            Request is the DJango request received for generating this javascript,
            with included user ip at request.ip.

        With this, and :py:meth:.authCallback method, we can add SSO engines
        to UDS with no much problems.
        """
        return None

    def auth_callback(
        self,
        parameters: 'types.auth.AuthCallbackParams',
        groups_manager: 'GroupsManager',
        request: 'types.requests.ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """
        There is a view inside UDS, an url, that will redirect the petition
        to this callback.

        If someone gets authenticated via this callback, the method will return
        an "username" must be return. This username will be used to:

           * Add user to UDS
           * Get user groups.

        So, if this callback is called, also get the membership to groups of the user, and keep them.
        This method will have to keep track of those until UDS request that groups
        using get_groups. (This is easy, using storage() provided with the environment (env())

        If this returns None, or empty, the authentication will be considered "invalid"
        and an error will be shown.

        Args:
            parameters: all GET and POST received parameters. Also has "_request" key, that points to HttpRequest
            groups_manager: Groups manager, you MUST check group membership using this gm
            request: ExtendedHttpRequest object

        Return:
            An AuthResult object, with:
                * success: True if authentication is valid, False otherwise
                * username: Username of the user, if success is True
                * url: Url to redirect to,

        Note:
            Keeping user information about group membership inside storage is highly recommended.
            There will be calls to get_groups one an again, and also to get_real_name, not just
            at login, but at future (from admin interface, at user editing for example)
        """
        return types.auth.FAILED_AUTH

    def get_info(
        self, parameters: collections.abc.Mapping[str, str]
    ) -> typing.Optional[tuple[str, typing.Optional[str]]]:
        """
        This method is invoked whenever the authinfo url is invoked, with the name of the authenticator
        If this is implemented, information returned by this will be shown via web.

        :note: You can return here a single element or a list (or tuple), where first element will be content itself,
               and second will be the content type (i.e. "text/plain").
        """
        return None

    def get_real_name(self, username: str) -> str:
        """
        Tries to get the real name of an user

        Default implementation returns just the same user name that is passed in.
        """
        return ''

    def create_user(self, user_data: dict[str, typing.Any]) -> None:
        """
        This method is used when creating an user to allow the authenticator:

            * Check that the name inside user_data is fine
            * Fill other (avoid modifying name, if you don't know what are you doing) user_data dictionary values.

        This will be invoked from admin interface, when admin wants to create a new user

        modified user_dta will be used to store values at database.

        Args:
            user_data: Contains data received from user directly, that is a dictionary
                with at least: name, real_name, comments, state & password.
                This is an in/out parameter, so you can modify, for example,
                **realName**

        Returns:
            Raises an exception if things didn't went fine,
            return value is ignored, but modified user_data is used if this does not
            raises an exception.

            Take care with whatever you modify here, you can even modify provided
            name (login name!) to a new one!

        Note:
            If you have an SSO where you can't create an user from admin interface,
            raise an exception here indicating that the creation can't be done.
            Default implementation simply raises "AuthenticatorException" and
            says that user can't be created manually

        """
        pass

    def modify_user(self, user_data: dict[str, str]) -> None:
        """
        This method is used when modifying an user to allow the authenticator:

            * Check that the name inside user_data is fine
            * Fill other (avoid modifying name, if you don't know what are you doing) user_data dictionary values.

        Args:
            user_data: Contains data received from user directly, that is a dictionary
                with at least: name, real_name, comments, state & password.
                This is an in/out parameter, so you can modify, for example,
                **realName**

        Returns:
            Raises an exception if things didn't went fine,
            return value is ignored, but modified user_data is used if this does not
            raises an exception.

            Take care with whatever you modify here, you can even modify provided
            name (login name!) to a new one!

        Note:
            By default, this will do nothing, as we can only modify "accesory" internal
            data of users.
        """

    def create_group(self, group_data: dict[str, str]) -> None:
        """
        This method is used when creating a new group to allow the authenticator:

            * Check that the name inside group_data is fine
            * Fill other (not name, if you don't know what are you doing) user_data dictionary values.

        This will be invoked from admin interface, when admin wants to create a new group.

        modified group_data will be used to store values at database.

        Args:
            group_data: Contains data received from interface directly, that is a dictionary
                       with at least: name, comments and state. (State.ACTIVE, State.INACTIVE)
                       This is an in/out parameter, so you can modify, for example,
                       **comments**
                       (it's the "fields" from the admin form)

        Returns:
            Raises an exception if things didn't went fine,
            return value is ignored, but modified group_data is used if this does not
            raises an exception.

        Note:
            Take care with whatever you modify here, you can even modify provided
            name (group name) to a new one!
        """

    def modify_group(self, group_data: dict[str, str]) -> None:
        """
        This method is used when modifying group to allow the authenticator:

            * Check that the name inside group_data is fine
            * Fill other (not name, if you don't know what are you doing) usr_data dictionary values.

        This will be invoked from admin interface, when admin wants to create a new group.

        modified group_data will be used to store values at database.

        Args:
            group_data: Contains data received from user directly, that is a dictionary
                       with at least: name, comments and state. (State.ACTIVE, State.INACTIVE)
                       This is an in/out parameter, so you can modify, for example,
                       **comments**

        Returns:
            Raises an exception if things didn't went fine,
            return value is ignored, but modified group_data is used if this does not
            raises an exception.

        Note: 'name' output parameter will be ignored
        """

    def remove_user(self, username: str) -> None:
        """
        Remove user is used whenever from the administration interface, or from other
        internal workers, an user needs to be removed.

        This is a notification method, whenever an user gets removed from UDS, this
        will get called.

        You can do here whatever you want, but you are not requested to do anything
        at your authenticators.

        If this method raises an exception, the user will not be removed from UDS
        """

    # We don't have a "modify" group option. Once u have created it, the only way of changing it if removing it an recreating it with another name

    def remove_group(self, groupname: str) -> None:
        """
        Remove user is used whenever from the administration interface, or from other
        internal workers, an group needs to be removed.

        This is a notification method, whenever an group gets removed from UDS, this
        will get called.

        You can do here whatever you want, but you are not requested to do anything
        at your authenticators.

        If this method raises an exception, the group will not be removed from UDS
        """
