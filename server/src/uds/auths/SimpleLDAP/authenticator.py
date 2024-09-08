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

import ldap  # pyright: ignore  # Needed to import ldap.filter without errors
import ldap.filter
from django.utils.translation import gettext_noop as _

from uds.core import auths, environment, types, exceptions
from uds.core.auths.auth import log_login
from uds.core.ui import gui
from uds.core.util import ensure, fields, ldaputil, validators

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
    username_attr = gui.TextField(
        length=64,
        label=_('User Name Attr'),
        default='uid',
        order=33,
        tooltip=_('Attributes that contains the user name (list of comma separated values)'),
        required=True,
        tab=_('Ldap info'),
    )
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

    _connection: typing.Optional['ldaputil.LDAPObject'] = None

    def initialize(self, values: typing.Optional[dict[str, typing.Any]]) -> None:
        if values:
            self.username_attr.value = self.username_attr.value.replace(' ', '')  # Removes white spaces
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

    def _get_connection(self) -> 'ldaputil.LDAPObject':
        """
        Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.
        @return: Connection established
        @raise exception: If connection could not be established
        """
        if self._connection is None:  # We are not connected
            self._connection = ldaputil.connection(
                self.username.as_str(),
                self.password.as_str(),
                self.host.as_str(),
                port=self.port.as_int(),
                ssl=self.use_ssl.as_bool(),
                timeout=self.timeout.as_int(),
                debug=False,
                verify_ssl=self.verify_ssl.as_bool(),
                certificate=self.certificate.as_str(),
            )

        return self._connection

    def _connect_as(self, username: str, password: str) -> typing.Any:
        return ldaputil.connection(
            username,
            password,
            self.host.as_str(),
            port=self.port.as_int(),
            ssl=self.use_ssl.as_bool(),
            timeout=self.timeout.as_int(),
            debug=False,
            verify_ssl=self.verify_ssl.as_bool(),
            certificate=self.certificate.as_str(),
        )

    def _get_user(self, username: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searchs for the username and returns its LDAP entry
        @param username: username to search, using user provided parameters at configuration to map search entries.
        @return: None if username is not found, an dictionary of LDAP entry attributes if found.
        @note: Active directory users contains the groups it belongs to in "memberOf" attribute
        """
        attributes = self.username_attr.as_str().split(',') + [self.user_id_attr.as_str()]
        if self.mfa_attribute.as_str():
            attributes = attributes + [self.mfa_attribute.as_str()]

        return ldaputil.first(
            con=self._get_connection(),
            base=self.ldap_base.as_str(),
            objectClass=self.user_class.as_str(),
            field=self.user_id_attr.as_str(),
            value=username,
            attributes=attributes,
            sizeLimit=LDAP_RESULT_LIMIT,
        )

    def _get_group(self, groupName: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searchs for the groupName and returns its LDAP entry
        @param groupName: group name to search, using user provided parameters at configuration to map search entries.
        @return: None if group name is not found, an dictionary of LDAP entry attributes if found.
        """
        return ldaputil.first(
            con=self._get_connection(),
            base=self.ldap_base.as_str(),
            objectClass=self.group_class.as_str(),
            field=self.group_id_attr.as_str(),
            value=groupName,
            attributes=[self.member_attr.as_str()],
            sizeLimit=LDAP_RESULT_LIMIT,
        )

    def _get_groups(self, user: ldaputil.LDAPResultType) -> list[str]:
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
            logger.exception('Exception at __getGroups')
            return []

    def _get_user_realname(self, usr: ldaputil.LDAPResultType) -> str:
        '''
        Tries to extract the real name for this user. Will return all atttributes (joint)
        specified in _userNameAttr (comma separated).
        '''
        return ' '.join(
            [
                (
                    ' '.join((str(k) for k in usr.get(id_, '')))
                    if isinstance(usr.get(id_), list)
                    else str(usr.get(id_, ''))
                )
                for id_ in self.username_attr.as_str().split(',')
            ]
        ).strip()

    def authenticate(
        self,
        username: str,
        credentials: str,
        groups_manager: 'auths.GroupsManager',
        request: 'ExtendedHttpRequest',
    ) -> types.auth.AuthenticationResult:
        '''
        Must authenticate the user.
        We can have to different situations here:
           1.- The authenticator is external source, what means that users may be unknown to system before callig this
           2.- The authenticator isn't external source, what means that users have been manually added to system and are known before this call
        We receive the username, the credentials used (normally password, but can be a public key or something related to pk) and a group manager.
        The group manager is responsible for letting know the authenticator which groups we currently has active.
        @see: uds.core.auths.groups_manager
        '''
        try:
            # Locate the user at LDAP
            user = self._get_user(username)

            if user is None:
                log_login(request, self.db_obj(), username, 'Invalid user')
                return types.auth.FAILED_AUTH

            try:
                # Let's see first if it credentials are fine
                self._connect_as(user['dn'], credentials)  # Will raise an exception if it can't connect
            except Exception:
                log_login(request, self.db_obj(), username, 'Invalid password')
                return types.auth.FAILED_AUTH

            # store the user mfa attribute if it is set
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
        '''
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception (AuthException) it things didn't went fine
        '''
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
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        Modify user has no reason on external sources, so it will never be used (probably)
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception it things don't goes fine
        '''
        return self.create_user(user_data)

    def create_group(self, group_data: dict[str, str]) -> None:
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has its own groups and, at most, it can check if it exists on external source before accepting it
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @params groupData: a dict that has, at least, name, comments and active
        @return:  Raises an exception it things don't goes fine
        '''
        res = self._get_group(group_data['name'])
        if res is None:
            raise exceptions.auth.AuthenticatorException(_('Group not found'))

    def get_groups(self, username: str, groups_manager: 'auths.GroupsManager') -> None:
        '''
        Looks for the real groups to which the specified user belongs
        Updates groups manager with valid groups
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        '''
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
            auth = SimpleLDAPAuthenticator(None, env, data)  # type: ignore
            return auth.test_connection()
        except Exception as e:
            logger.error("Exception found testing Simple LDAP auth: %s", e)
            return types.core.TestResult(False, _('Error testing connection'))

    def test_connection(self) -> types.core.TestResult:
        try:
            con = self._get_connection()
        except Exception as e:
            return types.core.TestResult(False, str(e))

        try:
            con.search_s(  # pyright: ignore reportGeneralTypeIssues
                base=self.ldap_base.as_str(),
                scope=ldaputil.SCOPE_BASE,  # pyright: ignore reportGeneralTypeIssues
            )

        except Exception:
            return types.core.TestResult(False, _('Ldap search base is incorrect'))

        try:
            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                            filterstr=f'(objectClass={self.user_class.as_str()})',
                            sizelimit=1,
                        )
                    )
                )
                != 1
            ):
                raise Exception(_('Ldap user class seems to be incorrect (no user found by that class)'))

            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                            filterstr=f'(objectClass={self.group_class.as_str()})',
                            sizelimit=1,
                        )
                    )
                )
                != 1
            ):
                raise Exception(_('Ldap group class seems to be incorrect (no group found by that class)'))

            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                            filterstr=f'({self.user_id_attr.as_str()}=*)',
                            sizelimit=1,
                        )
                    )
                )
                != 1
            ):
                raise Exception(
                    _('Ldap user id attribute seems to be incorrect (no user found by that attribute)')
                )

            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                            filterstr=f'({self.group_id_attr.as_str()}=*)',
                            sizelimit=1,
                        )
                    )
                )
                != 1
            ):
                raise Exception(
                    _('Ldap group id attribute seems to be incorrect (no group found by that attribute)')
                )

            if (
                len(
                    ensure.as_list(
                        con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                            base=self.ldap_base.as_str(),
                            scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                            filterstr=f'(&(objectClass={self.user_class.as_str()})({self.user_id_attr.as_str()}=*))',
                            sizelimit=1,
                        )
                    )
                )
                != 1
            ):
                raise Exception(
                    _(
                        'Ldap user class or user id attr is probably wrong (can\'t find any user with both conditions)'
                    )
                )

            res = ensure.as_list(
                con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
                    base=self.ldap_base.as_str(),
                    scope=ldaputil.SCOPE_SUBTREE,  # pyright: ignore reportGeneralTypeIssues
                    filterstr=f'(&(objectClass={self.group_class.as_str()})({self.group_id_attr.as_str()}=*))',
                    attrlist=[self.member_attr.as_str()],
                )
            )
            if not res:
                raise Exception(
                    _(
                        'Ldap group class or group id attr is probably wrong (can\'t find any group with both conditions)'
                    )
                )
            ok = False
            for r in res:
                if self.member_attr.as_str() in r[1]:
                    ok = True
                    break
            if ok is False:
                raise Exception(_('Can\'t locate any group with the membership attribute specified'))
        except Exception as e:
            return types.core.TestResult(False, str(e))

        return types.core.TestResult(True)

    def __str__(self) -> str:
        return (
            f'Ldap Auth: {self.username.as_str()}:{self.password.as_str()}@{self.host.as_str()}:{self.port.as_int()}, '
            f'base = {self.ldap_base.as_str()}, userClass = {self.user_class.as_str()}, groupClass = {self.group_class.as_str()}, '
            f'userIdAttr = {self.user_id_attr.as_str()}, groupIdAttr = {self.group_id_attr.as_str()}, '
            f'memberAttr = {self.member_attr.as_str()}, userName attr = {self.username_attr.as_str()}'
        )
