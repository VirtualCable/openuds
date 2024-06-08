# pylint: disable=no-member

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import auths, environment, exceptions, types
from uds.core.auths.auth import log_login
from uds.core.ui import gui
from uds.core.util import ensure, ldaputil, auth as auth_utils, fields

try:
    # pylint: disable=no-name-in-module
    from . import extra  # type: ignore
except Exception:
    extra = None

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)

LDAP_RESULT_LIMIT = 100


class RegexLdap(auths.Authenticator):
    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('Ldap Server Host'),
        required=True,
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        default=389,
        order=2,
        tooltip=_('Ldap port (usually 389 for non ssl and 636 for ssl)'),
        required=True,
    )
    use_ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=3,
        tooltip=_('If checked, the connection will be ssl, using port 636 instead of 389'),
    )
    username = gui.TextField(
        length=64,
        label=_('User'),
        order=4,
        tooltip=_('Username with read privileges on the base selected'),
        required=True,
        tab=types.ui.Tab.CREDENTIALS,
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=5,
        tooltip=_('Password of the ldap user'),
        required=True,
        tab=types.ui.Tab.CREDENTIALS,
    )

    timeout = fields.timeout_field(tab=None, default=10)  # Use "main tab"
    verify_ssl = fields.verify_ssl_field(order=11)

    certificate = gui.TextField(
        length=8192,
        lines=4,
        label=_('Certificate'),
        order=12,
        tooltip=_('Certificate to use for SSL verification'),
        required=False,
        tab=types.ui.Tab.ADVANCED,
    )
    ldap_base = gui.TextField(
        length=64,
        label=_('Base'),
        order=20,
        tooltip=_('Common search base (used for "users" and "groups")'),
        required=True,
        tab=_('Ldap info'),
    )
    user_class = gui.TextField(
        length=64,
        label=_('User class'),
        default='posixAccount',
        order=21,
        tooltip=_('Class for LDAP users (normally posixAccount)'),
        required=True,
        tab=_('Ldap info'),
    )
    userid_attr = gui.TextField(
        length=64,
        label=_('User Id Attr'),
        default='uid',
        order=22,
        tooltip=_('Attribute that contains the user id.'),
        required=True,
        tab=_('Ldap info'),
    )
    username_attr = gui.TextField(
        length=640,
        label=_('User Name Attr'),
        lines=2,
        default='uid',
        order=23,
        tooltip=_(
            'Attributes that contains the user name attributes or attribute patterns (one for each line)'
        ),
        required=True,
        tab=_('Ldap info'),
    )
    groupname_attr = gui.TextField(
        length=640,
        label=_('Group Name Attr'),
        lines=2,
        default='cn',
        order=24,
        tooltip=_(
            'Attribute that contains the group name attributes or attribute patterns (one for each line)'
        ),
        required=True,
        tab=_('Ldap info'),
    )
    # regex = gui.TextField(length=64, label = _('Regular Exp. for groups'), defvalue = '^(.*)', order = 12, tooltip = _('Regular Expression to extract the group name'), required = True)

    alternate_class = gui.TextField(
        length=64,
        label=_('Alt. class'),
        default='',
        order=25,
        tooltip=_('Class for LDAP objects that will be also checked for groups retrieval (normally empty)'),
        required=False,
        tab=_('Advanced'),
    )

    mfa_attribute = fields.mfa_attr_field()

    type_name = _('Regex LDAP Authenticator')
    type_type = 'RegexLdapAuthenticator'
    type_description = _('Regular Expressions LDAP authenticator')
    icon_file = 'auth.png'

    # If it has and external source where to get "new" users (groups must be declared inside UDS)
    # If we need to enter the password for this user
    needs_password = False
    # Label for username field
    label_username = _('Username')
    # Label for group field
    label_groupname = _("Group")
    # Label for password field
    label_password = _("Password")

    _connection: typing.Optional['ldaputil.LDAPObject'] = None

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        if values:
            auth_utils.validate_regex_field(self.username_attr)
            auth_utils.validate_regex_field(self.groupname_attr)

    def mfa_storage_key(self, username: str) -> str:
        return 'mfa_' + self.db_obj().uuid + username

    def mfa_identifier(self, username: str) -> str:
        return self.storage.read_pickled(self.mfa_storage_key(username)) or ''

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.decode('utf8').split('\t')

        self.verify_ssl.value = False  # Backward compatibility
        self.mfa_attribute.value = ''  # Backward compatibility
        self.certificate.value = ''  # Backward compatibility

        # Common values
        self.host.value = vals[1]
        self.port.value = int(vals[2])
        self.use_ssl.value = gui.as_bool(vals[3])
        self.username.value = vals[4]
        self.password.value = vals[5]
        self.timeout.value = int(vals[6])
        self.ldap_base.value = vals[7]
        self.user_class.value = vals[8]
        self.userid_attr.value = vals[9]
        self.groupname_attr.value = vals[10]

        logger.debug('Common: %s', vals[1:11])

        if vals[0] == 'v1':
            logger.debug("Data: %s", vals[11:])
            # Adds username and fix groupname
            regex, self.username_attr.value = vals[11:]
            # append the regex to the groupname_attr, now it is a multiline field if regex is not empty
            if regex:
                self.groupname_attr.value = self.groupname_attr.value + '=' + regex
            # Transform comma separated values to multiline
            self.username_attr.value = '\n'.join(self.username_attr.value.split(','))
        elif vals[0] == 'v2':
            logger.debug("Data v2: %s", vals[1:])
            self.username_attr.value = vals[11]
        elif vals[0] == 'v3':
            logger.debug("Data v3: %s", vals[1:])
            (
                self.username_attr.value,
                self.alternate_class.value,
            ) = vals[11:]
        elif vals[0] == 'v4':
            logger.debug("Data v4: %s", vals[1:])
            (
                self.username_attr.value,
                self.alternate_class.value,
                self.mfa_attribute.value,
            ) = vals[11:]
        elif vals[0] == 'v5':
            logger.debug("Data v5: %s", vals[1:])
            self.username_attr.value = vals[11]
            self.alternate_class.value = vals[12]
            self.mfa_attribute.value = vals[13]
            self.verify_ssl.value = gui.as_bool(vals[14])
            self._certificate = vals[15]

        self.mark_for_upgrade()  # Old version, so flag for upgrade if possible

    def _stablish_connection(self) -> 'ldaputil.LDAPObject':
        """
        Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.
        @return: Connection established
        @raise exception: If connection could not be established
        """
        if self._connection is None:  # If connection is not established, try to connect
            self._connection = ldaputil.connection(
                self.username.as_str(),
                self.password.as_str(),
                self.host.as_str(),
                port=int(self.port.as_int()),
                ssl=self.use_ssl.as_bool(),
                timeout=int(self.timeout.as_int()),
                debug=False,
            )

        return self._connection

    def _stablish_connection_as(self, username: str, password: str) -> 'ldaputil.LDAPObject':
        return ldaputil.connection(
            username,
            password,
            self.host.as_str(),
            port=int(self.port.as_int()),
            ssl=self.use_ssl.as_bool(),
            timeout=int(self.timeout.as_int()),
            debug=False,
        )

    def _get_user(self, username: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searchs for the username and returns its LDAP entry
        @param username: username to search, using user provided parameters at configuration to map search entries.
        @return: None if username is not found, an dictionary of LDAP entry attributes if found.
        @note: Active directory users contains the groups it belongs to in "memberOf" attribute
        """
        attributes = (
            [self.userid_attr.as_str()]
            + list(auth_utils.get_attributes_regex_field(self.username_attr))
            + list(auth_utils.get_attributes_regex_field(self.groupname_attr))
        )
        if self.mfa_attribute.value:
            attributes = attributes + list(auth_utils.get_attributes_regex_field(self.mfa_attribute))

        user = ldaputil.first(
            con=self._stablish_connection(),
            base=self.ldap_base.as_str(),
            objectClass=self.user_class.as_str(),
            field=self.userid_attr.as_str(),
            value=username,
            attributes=attributes,
            sizeLimit=LDAP_RESULT_LIMIT,
        )

        # If user attributes is split, that is, it has more than one "ldap entry", get a second entry filtering by a new attribute
        # and add result attributes to "main" search.
        # For example, you can have authentication in an "user" object class and attributes in an "user_attributes" object class.
        # Note: This is very rare situation, but it ocurrs :)
        if user and self.alternate_class.value.strip():
            for usr in ldaputil.as_dict(
                con=self._stablish_connection(),
                base=self.ldap_base.as_str(),
                ldap_filter=f'(&(objectClass={self.alternate_class.value.strip()})({self.userid_attr.as_str()}={ldaputil.escape(username)}))',
                attributes=attributes,
                limit=LDAP_RESULT_LIMIT,
            ):
                for attr_name in auth_utils.get_attributes_regex_field(self.groupname_attr.as_str()):
                    v = usr.get(attr_name)
                    if not v:
                        continue
                    norm_attrname = attr_name.lower()
                    # If already exists the field, check if it is a list to add new elements...
                    if norm_attrname in usr:
                        # Convert existing to list, so we can add a new value
                        if not isinstance(user[norm_attrname], (list, tuple)):
                            user[norm_attrname] = [user[norm_attrname]]

                        # Convert values to list, if not list
                        if not isinstance(v, collections.abc.Iterable):
                            v = [v]

                        # Now append to existing values
                        for x in typing.cast(typing.Iterable[str], v):
                            user[norm_attrname].append(x)
                    else:
                        user[norm_attrname] = v

        return user

    def _get_groups(self, user: ldaputil.LDAPResultType) -> list[str]:
        grps = auth_utils.process_regex_field(self.groupname_attr.as_str(), user)
        if extra:
            try:
                grps += typing.cast(list[str], extra.get_groups(self, user))  # pyright: ignore
            except Exception:
                logger.exception('Exception getting extra groups')
        return grps

    def _get_real_name(self, user: ldaputil.LDAPResultType) -> str:
        return ' '.join(auth_utils.process_regex_field(self.username_attr.value, user))

    def authenticate(
        self,
        username: str,
        credentials: str,
        groups_manager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """
        Must authenticate the user.
        We can have to different situations here:
           1.- The authenticator is external source, what means that users may be unknown to system before callig this
           2.- The authenticator isn't external source, what means that users have been manually added to system and are known before this call
        We receive the username, the credentials used (normally password, but can be a public key or something related to pk) and a group manager.
        The group manager is responsible for letting know the authenticator which groups we currently has active.
        @see: uds.core.auths.groups_manager
        """
        try:
            # Locate the user at LDAP
            usr = self._get_user(username)

            if usr is None:
                log_login(request, self.db_obj(), username, 'Invalid user')
                return types.auth.FAILED_AUTH

            try:
                # Let's see first if it credentials are fine
                self._stablish_connection_as(
                    usr['dn'], credentials
                )  # Will raise an exception if it can't connect
            except Exception:
                log_login(request, self.db_obj(), username, 'Invalid password')
                return types.auth.FAILED_AUTH

            # store the user mfa attribute if it is set
            if self.mfa_attribute.value:
                self.storage.save_pickled(
                    self.mfa_storage_key(username),
                    usr[self.mfa_attribute.value][0],
                )

            groups_manager.validate(self._get_groups(usr))

            return types.auth.SUCCESS_AUTH

        except Exception:
            return types.auth.FAILED_AUTH

    def create_user(self, user_data: dict[str, str]) -> None:
        """
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has the user  cause they are managed externally, so, it can at most test if the users exists on external source
        before accepting it.
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param user_data: Contains data received from user directly, that is, a dictionary with at least: name, real_name, comments, state & password
        @return:  Raises an exception (AuthException) it things didn't went fine
        """
        res = self._get_user(user_data['name'])
        if res is None:
            raise exceptions.auth.AuthenticatorException(_('Username not found'))
        # Fills back realName field
        user_data['real_name'] = self._get_real_name(res)

    def get_real_name(self, username: str) -> str:
        """
        Tries to get the real name of an user
        """
        res = self._get_user(username)
        if res is None:
            return username
        return self._get_real_name(res)

    def modify_user(self, user_data: dict[str, str]) -> None:
        """
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        Modify user has no reason on external sources, so it will never be used (probably)
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param user_data: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception it things doesn't go fine
        """
        return self.create_user(user_data)

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        """
        Looks for the real groups to which the specified user belongs
        Updates groups manager with valid groups
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        """
        user = self._get_user(username)
        if user is None:
            raise exceptions.auth.AuthenticatorException(_('Username not found'))
        groups = self._get_groups(user)
        groups_manager.validate(groups)

    def search_users(self, pattern: str) -> collections.abc.Iterable[types.auth.SearchResultItem]:
        try:
            for r in ldaputil.as_dict(
                con=self._stablish_connection(),
                base=self.ldap_base.as_str(),
                ldap_filter=f'(&(&(objectClass={self.user_class.as_str()})({self.userid_attr.as_str()}={ldaputil.escape(pattern)}*)))',
                attributes=None,  # All attrs
                limit=LDAP_RESULT_LIMIT,
            ):
                logger.debug('Result: %s', r)
                yield types.auth.SearchResultItem(
                    id=r.get(self.userid_attr.as_str().lower(), [''])[0],
                    name=self._get_real_name(r),
                )
        except Exception as e:
            logger.exception("Exception: ")
            raise exceptions.auth.AuthenticatorException(_('Too many results, be more specific')) from e

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        try:
            auth = RegexLdap(None, env, data)  # type: ignore  # Regexldap does not use "dbAuth", so it's safe...
            return auth.test_connection()
        except Exception as e:
            logger.error('Exception found testing Simple LDAP auth %s: %s', e.__class__, e)
            return types.core.TestResult(False, f'Error testing connection: {e}')

    def test_connection(self) -> types.core.TestResult:
        try:
            con = self._stablish_connection()
        except Exception as e:
            return types.core.TestResult(False, f'Error connecting to ldap: {e}')

        try:
            con.search_s(  # pyright: ignore reportUnknownMemberType
                base=self.ldap_base.as_str(),
                scope=ldaputil.SCOPE_BASE,  # pyright: ignore reportUnknownMemberType
            )
        except Exception:
            return types.core.TestResult(False, _('Ldap search base is incorrect'))

        try:
            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportUnknownMemberType
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportUnknownMemberType
                            filterstr=f'(objectClass={self.user_class.as_str()})',
                            sizelimit=1,
                        )
                    )
                )
                == 1
            ):
                raise Exception()
            return types.core.TestResult(
                False, _('Ldap user class seems to be incorrect (no user found by that class)')
            )
        except Exception:  # nosec: Control flow
            # If found 1 or more, all right
            pass

        # Now test objectclass and attribute of users
        try:
            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportUnknownMemberType
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportUnknownMemberType
                            filterstr=f'(&(objectClass={self.user_class.as_str()})({self.userid_attr.as_str()}=*))',
                            sizelimit=1,
                        )
                    )
                )
                == 1
            ):
                raise Exception()
            return types.core.TestResult(
                False, _('Ldap user id attr is probably wrong (can\'t find any user with that attribute)')
            )
        except Exception:  # nosec: Control flow
            # If found 1 or more, all right
            pass

        for groupname_attr in self.groupname_attr.value.strip().split('\n'):
            vals = groupname_attr.split('=')[0]
            if vals == 'dn':
                continue
            try:
                if (
                    len(
                        ensure.as_list(
                            con.search_ext_s(  # pyright: ignore reportUnknownMemberType
                                base=self.ldap_base.as_str(),
                                scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportUnknownMemberType
                                filterstr=f'({vals}=*)',
                                sizelimit=1,
                            )
                        )
                    )
                    == 1
                ):
                    continue
            except Exception:  # nosec: Control flow
                continue
            return types.core.TestResult(
                False,
                _('Ldap group name attribute seems to be incorrect (no group found by that attribute)'),
            )

        # Now try to test regular expression to see if it matches anything (
        try:
            # Check the existence of at least a () grouping
            # Check validity of regular expression (try to compile it)
            # this only right now
            pass
        except Exception:  # nosec: Control flow
            pass

        return types.core.TestResult(True)

    def __str__(self) -> str:
        return (
            f'Ldap Auth: {self.username.as_str()}:{self.password.as_str()}@{self.host.as_str()}:{self.port.as_int()},'
            f' base = {self.ldap_base.as_str()}, user_class = {self.user_class.as_str()}, user_id_attr = {self.userid_attr.as_str()},'
            f' group_name_attr = {self.groupname_attr.as_str()}, user_name attr = {self.username_attr.value}, alternate_class={self.alternate_class.value}'
        )
