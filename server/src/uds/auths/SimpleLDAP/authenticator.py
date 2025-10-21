# pylint: disable=no-member   # ldap module gives errors to pylint
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from uds.core.util import ldaputil
from django.utils.translation import gettext_noop as _

from uds.core import auths, environment, types, exceptions
from uds.core.auths.auth import log_login
from uds.core.ui import gui
from uds.core.util import fields, ldaputil, validators, auth as auth_utils

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest

logger = logging.getLogger(__name__)

LDAP_RESULT_LIMIT = 100


# pylint: disable=too-many-instance-attributes
class SimpleLDAPAuthenticator(auths.Authenticator):
    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('Ldap Server IP or Hostname'),
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
        label=_('Ldap User'),
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
        order=30,
        tooltip=_('Common search base (used for "users" and "groups")'),
        required=True,
        tab=_('Ldap info'),
    )
    user_class = gui.TextField(
        length=64,
        label=_('User class'),
        default='posixAccount',
        order=31,
        tooltip=_('Class for LDAP users (normally posixAccount)'),
        required=True,
        tab=_('Ldap info'),
    )
    user_id_attr = gui.TextField(
        length=64,
        label=_('User Id Attr'),
        default='uid',
        order=32,
        tooltip=_('Attribute that contains the user id'),
        required=True,
        tab=_('Ldap info'),
    )
    username_attr = fields.realname_attr_field(tab=_('Ldap info'), order=33, default='uid')
    group_class = gui.TextField(
        length=64,
        label=_('Group class'),
        default='posixGroup',
        order=34,
        tooltip=_('Class for LDAP groups (normally poxisGroup)'),
        required=True,
        tab=_('Ldap info'),
    )
    group_id_attr = gui.TextField(
        length=64,
        label=_('Group Id Attr'),
        default='cn',
        order=35,
        tooltip=_('Attribute that contains the group id'),
        required=True,
        tab=_('Ldap info'),
    )
    member_attr = gui.TextField(
        length=64,
        label=_('Group membership attr'),
        default='memberUid',
        order=36,
        tooltip=_('Attribute of the group that contains the users belonging to it'),
        required=True,
        tab=_('Ldap info'),
    )
    mfa_attribute = gui.TextField(
        length=2048,
        lines=2,
        label=_('MFA attribute'),
        order=13,
        tooltip=_('Attribute from where to extract the MFA code'),
        required=False,
        tab=types.ui.Tab.MFA,
    )

    type_name = _('SimpleLDAP')
    type_type = 'SimpleLdapAuthenticator'
    type_description = _('Simple LDAP authenticator')
    icon_file = 'auth.png'

    # If it has and external source where to get "new" users (groups must be declared inside UDS)
    external_source = True
    # If we need to enter the password for this user
    needs_password = False
    # Label for username field
    label_username = _('Username')
    # Label for group field
    label_groupname = _("Group")
    # Label for password field
    label_password = _("Password")

    _connection: typing.Optional['ldaputil.LDAPConnection'] = None

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        if values:
            auth_utils.validate_regex_field(self.username_attr)
            validators.validate_certificate(self.certificate.value)

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        vals = data.decode('utf8').split('\t')

        self.verify_ssl.value = False  # Backward compatibility
        self.mfa_attribute.value = ''  # Backward compatibility
        self.certificate.value = ''  # Backward compatibility

        self.host.value = vals[1]
        self.port.value = int(vals[2])
        self.use_ssl.value = gui.as_bool(vals[3])
        self.username.value = vals[4]
        self.password.value = vals[5]
        self.timeout.value = int(vals[6])
        self.ldap_base.value = vals[7]
        self.user_class.value = vals[8]
        self.group_class.value = vals[9]
        self.user_id_attr.value = vals[10]
        self.group_id_attr.value = vals[11]
        self.member_attr.value = vals[12]
        self.username_attr.value = vals[13]

        # Upgrade to new format
        self.username_attr.value = '\n'.join(self.username_attr.value.split(','))

        logger.debug("Data: %s", vals[1:])

        if vals[0] == 'v2':
            self.mfa_attribute.value = vals[14]
            self.verify_ssl.value = gui.as_bool(vals[15])
            self.certificate.value = vals[16]

        self.mark_for_upgrade()

    def mfa_storage_key(self, username: str) -> str:
        return 'mfa_' + str(self.db_obj().uuid) + username

    def mfa_identifier(self, username: str) -> str:
        return self.storage.read_pickled(self.mfa_storage_key(username)) or ''

    def _get_connection(self) -> 'ldaputil.LDAPConnection':
        """
        Tries to connect to LDAP using ldaputil. If username is None, it tries to connect using user provided credentials.
        Returns:
            Connection established
        Raises:
            Exception if connection could not be established
        """
        if self._connection is None:
            self._connection = ldaputil.connection(
                username=self.username.as_str(),
                passwd=self.password.as_str(),
                host=self.host.as_str(),
                port=self.port.as_int(),
                use_ssl=self.use_ssl.as_bool(),
                timeout=self.timeout.as_int(),
                debug=False,
                verify_ssl=self.verify_ssl.as_bool(),
                certificate_data=self.certificate.as_str(),
            )
        return self._connection

    def _connect_as(self, username: str, password: str) -> typing.Any:
        return ldaputil.connection(
            username=username,
            passwd=password,
            host=self.host.as_str(),
            port=self.port.as_int(),
            use_ssl=self.use_ssl.as_bool(),
            timeout=self.timeout.as_int(),
            debug=False,
            verify_ssl=self.verify_ssl.as_bool(),
            certificate_data=self.certificate.as_str(),
        )

    def _get_user(self, username: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searches for the username and returns its LDAP entry.
        Args:
            username: username to search, using user provided parameters at configuration to map search entries.
        Returns:
            None if username is not found, a dictionary of LDAP entry attributes if found.
        Note:
            Active directory users contain the groups it belongs to in "memberOf" attribute
        """
        attributes = self.username_attr.as_str().split(',') + [self.user_id_attr.as_str()]
        if self.mfa_attribute.as_str():
            attributes = attributes + [self.mfa_attribute.as_str()]
        return ldaputil.first(
            con=self._get_connection(),
            base=self.ldap_base.as_str(),
            object_class=self.user_class.as_str(),
            field=self.user_id_attr.as_str(),
            value=username,
            attributes=attributes,
            max_entries=LDAP_RESULT_LIMIT,
        )

    def _get_group(self, groupname: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searches for the groupname and returns its LDAP entry.
        Args:
            groupname (str): groupname to search, using user provided parameters at configuration to map search entries.
        Returns:
            typing.Optional[ldaputil.LDAPResultType]: None if groupname is not found, a dictionary of LDAP entry attributes if found.
        """
        return ldaputil.first(
            con=self._get_connection(),
            base=self.ldap_base.as_str(),
            object_class=self.group_class.as_str(),
            field=self.group_id_attr.as_str(),
            value=groupname,
            attributes=[self.member_attr.as_str()],
            max_entries=LDAP_RESULT_LIMIT,
        )

    def _get_groups(self, user: ldaputil.LDAPResultType) -> list[str]:
        """
        Searches for the groups the user belongs to and returns a list of group names.
        Args:
            user (ldaputil.LDAPResultType): The user to search for groups
        Returns:
            list[str]: A list of group names the user belongs to
        """
        try:
            groups: list[str] = []
            filter_ = f'(&(objectClass={self.group_class.as_str()})(|({self.member_attr.as_str()}={user["_id"]})({self.member_attr.as_str()}={user["dn"]})))'
            for d in ldaputil.as_dict(
                con=self._get_connection(),
                base=self.ldap_base.as_str(),
                ldap_filter=filter_,
                attributes=[self.group_id_attr.as_str()],
                limit=10 * LDAP_RESULT_LIMIT,
            ):
                if self.group_id_attr.as_str() in d:
                    for k in d[self.group_id_attr.as_str()]:
                        groups.append(k)
            logger.debug('Groups: %s', groups)
            return groups
        except Exception:
            logger.exception('Exception at _get_groups')
            return []

    def _get_user_realname(self, user: ldaputil.LDAPResultType) -> str:
        """
        Tries to extract the real name for this user. Will return all attributes (joined)
        specified in username_attr (comma separated).
        """
        return ' '.join(auth_utils.process_regex_field(self.username_attr.value, user))

    def authenticate(
        self,
        username: str,
        credentials: str,
        groups_manager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        """
        Authenticates the user using ldaputil.
        """
        try:
            user = self._get_user(username)
            if user is None:
                log_login(request, self.db_obj(), username, 'Invalid user', as_error=True)
                return types.auth.FAILED_AUTH
            try:
                self._connect_as(user['dn'], credentials)
            except Exception:
                log_login(request, self.db_obj(), username, 'Invalid password', as_error=True)
                return types.auth.FAILED_AUTH
            if self.mfa_attribute.as_str():
                self.storage.save_pickled(
                    self.mfa_storage_key(username),
                    user[self.mfa_attribute.as_str()][0],
                )
            groups_manager.validate(self._get_groups(user))
            return types.auth.SUCCESS_AUTH
        except Exception:
            return types.auth.FAILED_AUTH

    def create_user(self, user_data: dict[str, str]) -> None:
        res = self._get_user(user_data['name'])
        if res is None:
            raise exceptions.auth.AuthenticatorException(_('Username not found'))
        # Fills back realName field
        user_data['real_name'] = self._get_user_realname(res)

    def get_real_name(self, username: str) -> str:
        '''
        Tries to get the real name of an user
        '''
        res = self._get_user(username)
        if res is None:
            return username
        return self._get_user_realname(res)

    def modify_user(self, user_data: dict[str, str]) -> None:
        return self.create_user(user_data)

    def create_group(self, group_data: dict[str, str]) -> None:
        res = self._get_group(group_data['name'])
        if res is None:
            raise exceptions.auth.AuthenticatorException(_('Group not found'))

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        user = self._get_user(username)
        if user is None:
            raise exceptions.auth.AuthenticatorException(_('Username not found'))
        groups_manager.validate(self._get_groups(user))

    def search_users(self, pattern: str) -> collections.abc.Iterable[types.auth.SearchResultItem]:
        try:
            return [
                types.auth.SearchResultItem(
                    id=r[self.user_id_attr.as_str()][0], name=self._get_user_realname(r)
                )
                for r in ldaputil.as_dict(
                    con=self._get_connection(),
                    base=self.ldap_base.as_str(),
                    ldap_filter=f'(&(objectClass={self.user_class.as_str()})({self.user_id_attr.as_str()}={pattern}*))',
                    attributes=[self.user_id_attr.as_str(), self.username_attr.as_str()],
                    limit=LDAP_RESULT_LIMIT,
                )
            ]
        except Exception as e:
            logger.exception("Exception: ")
            raise exceptions.auth.AuthenticatorException(_('Too many results, be more specific')) from e

    def search_groups(self, pattern: str) -> collections.abc.Iterable[types.auth.SearchResultItem]:
        try:
            return [
                types.auth.SearchResultItem(id=r[self.group_id_attr.as_str()][0], name=r['description'][0])
                for r in ldaputil.as_dict(
                    con=self._get_connection(),
                    base=self.ldap_base.as_str(),
                    ldap_filter=f'(&(objectClass={self.group_class.as_str()})({self.group_id_attr.as_str()}={pattern}*))',
                    attributes=[self.group_id_attr.as_str(), 'memberOf', 'description'],
                    limit=LDAP_RESULT_LIMIT,
                )
            ]
        except Exception as e:
            logger.exception("Exception: ")
            raise exceptions.auth.AuthenticatorException(_('Too many results, be more specific')) from e

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        try:
            auth = SimpleLDAPAuthenticator(env, data)
            return auth.test_connection()
        except Exception as e:
            logger.error("Exception found testing Simple LDAP auth: %s", e)
            return types.core.TestResult(False, _('Error testing connection'))

    def test_connection(self) -> types.core.TestResult:
        try:
            con = self._get_connection()
        except Exception as e:
            return types.core.TestResult(False, str(e))

        # Test base search
        try:
            next(ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                '(objectClass=*)',
                limit=1,
                scope=ldaputil.SCOPE_BASE,
            ))
        except Exception:
            return types.core.TestResult(False, _('Ldap search base is incorrect'))

        # Test user class
        try:
            count = sum(1 for _ in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'(objectClass={self.user_class.as_str()})',
                limit=1,
                scope=ldaputil.SCOPE_SUBTREE,
            ))
            if count == 0:
                return types.core.TestResult(False, _('Ldap user class seems to be incorrect (no user found by that class)'))
        except Exception:
            pass

        # Test group class
        try:
            count = sum(1 for _ in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'(objectClass={self.group_class.as_str()})',
                limit=1,
                scope=ldaputil.SCOPE_SUBTREE,
            ))
            if count == 0:
                return types.core.TestResult(False, _('Ldap group class seems to be incorrect (no group found by that class)'))
        except Exception:
            pass

        # Test user id attribute
        try:
            count = sum(1 for _ in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'({self.user_id_attr.as_str()}=*)',
                limit=1,
                scope=ldaputil.SCOPE_SUBTREE,
            ))
            if count == 0:
                return types.core.TestResult(False, _('Ldap user id attribute seems to be incorrect (no user found by that attribute)'))
        except Exception:
            pass

        # Test group id attribute
        try:
            count = sum(1 for _ in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'({self.group_id_attr.as_str()}=*)',
                limit=1,
                scope=ldaputil.SCOPE_SUBTREE,
            ))
            if count == 0:
                return types.core.TestResult(False, _('Ldap group id attribute seems to be incorrect (no group found by that attribute)'))
        except Exception:
            pass

        # Test user class and user id attribute together
        try:
            count = sum(1 for _ in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'(&(objectClass={self.user_class.as_str()})({self.user_id_attr.as_str()}=*))',
                limit=1,
                scope=ldaputil.SCOPE_SUBTREE,
            ))
            if count == 0:
                return types.core.TestResult(False, _('Ldap user class or user id attr is probably wrong (can\'t find any user with both conditions)'))
        except Exception:
            pass

        # Test group class and group id attribute together
        try:
            found = False
            for r in ldaputil.as_dict(
                con,
                self.ldap_base.as_str(),
                f'(&(objectClass={self.group_class.as_str()})({self.group_id_attr.as_str()}=*))',
                attributes=[self.member_attr.as_str()],
                limit=LDAP_RESULT_LIMIT,
                scope=ldaputil.SCOPE_SUBTREE,
            ):
                if self.member_attr.as_str() in r:
                    found = True
                    break
            if not found:
                return types.core.TestResult(False, _('Can\'t locate any group with the membership attribute specified'))
        except Exception as e:
            return types.core.TestResult(False, str(e))

        return types.core.TestResult(True)

    def __str__(self) -> str:
        return (
            f'Ldap Auth: {self.username.as_str()}:{self.password.as_str()}@{self.host.as_str()}:{self.port.as_int()}, '
            f'base = {self.ldap_base.as_str()}, user_class = {self.user_class.as_str()}, group_class = {self.group_class.as_str()}, '
            f'userIdAttr = {self.user_id_attr.as_str()}, group_id_attr = {self.group_id_attr.as_str()}, '
            f'memberAttr = {self.member_attr.as_str()}, username attr = {self.username_attr.as_str()}'
        )
