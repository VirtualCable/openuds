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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

import ldap.filter
import ldap

from django.utils.translation import gettext_noop as _

from uds.core.ui import gui
from uds.core import auths
from uds.core.util import ldaputil
from uds.core.auths.auth import authLogLogin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest

logger = logging.getLogger(__name__)

LDAP_RESULT_LIMIT = 100


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
        defvalue='389',
        order=2,
        tooltip=_('Ldap port (usually 389 for non ssl and 636 for ssl)'),
        required=True,
    )
    ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=3,
        tooltip=_(
            'If checked, the connection will be ssl, using port 636 instead of 389'
        ),
    )
    username = gui.TextField(
        length=64,
        label=_('Ldap User'),
        order=4,
        tooltip=_('Username with read privileges on the base selected'),
        required=True,
        tab=gui.CREDENTIALS_TAB,
    )
    password = gui.PasswordField(
        lenth=32,
        label=_('Password'),
        order=5,
        tooltip=_('Password of the ldap user'),
        required=True,
        tab=gui.CREDENTIALS_TAB,
    )
    timeout = gui.NumericField(
        length=3,
        label=_('Timeout'),
        defvalue='10',
        order=6,
        tooltip=_('Timeout in seconds of connection to LDAP'),
        required=True,
        minValue=1,
    )
    ldapBase = gui.TextField(
        length=64,
        label=_('Base'),
        order=7,
        tooltip=_('Common search base (used for "users" and "groups")'),
        required=True,
        tab=_('Ldap info'),
    )
    userClass = gui.TextField(
        length=64,
        label=_('User class'),
        defvalue='posixAccount',
        order=8,
        tooltip=_('Class for LDAP users (normally posixAccount)'),
        required=True,
        tab=_('Ldap info'),
    )
    userIdAttr = gui.TextField(
        length=64,
        label=_('User Id Attr'),
        defvalue='uid',
        order=9,
        tooltip=_('Attribute that contains the user id'),
        required=True,
        tab=_('Ldap info'),
    )
    userNameAttr = gui.TextField(
        length=64,
        label=_('User Name Attr'),
        defvalue='uid',
        order=10,
        tooltip=_(
            'Attributes that contains the user name (list of comma separated values)'
        ),
        required=True,
        tab=_('Ldap info'),
    )
    groupClass = gui.TextField(
        length=64,
        label=_('Group class'),
        defvalue='posixGroup',
        order=11,
        tooltip=_('Class for LDAP groups (normally poxisGroup)'),
        required=True,
        tab=_('Ldap info'),
    )
    groupIdAttr = gui.TextField(
        length=64,
        label=_('Group Id Attr'),
        defvalue='cn',
        order=12,
        tooltip=_('Attribute that contains the group id'),
        required=True,
        tab=_('Ldap info'),
    )
    memberAttr = gui.TextField(
        length=64,
        label=_('Group membership attr'),
        defvalue='memberUid',
        order=13,
        tooltip=_('Attribute of the group that contains the users belonging to it'),
        required=True,
        tab=_('Ldap info'),
    )

    typeName = _('SimpleLDAP (DEPRECATED)')
    typeType = 'SimpleLdapAuthenticator'
    typeDescription = _('Simple LDAP authenticator (DEPRECATED)')
    iconFile = 'auth.png'

    # If it has and external source where to get "new" users (groups must be declared inside UDS)
    isExternalSource = True
    # If we need to enter the password for this user
    needsPassword = False
    # Label for username field
    userNameLabel = _('Username')
    # Label for group field
    groupNameLabel = _("Group")
    # Label for password field
    passwordLabel = _("Password")

    _connection: typing.Any = None
    _host: str = ''
    _port: str = ''
    _ssl: bool = False
    _username: str = ''
    _password: str = ''
    _timeout: str = ''
    _ldapBase: str = ''
    _userClass: str = ''
    _groupClass: str = ''
    _userIdAttr: str = ''
    _groupIdAttr: str = ''
    _memberAttr: str = ''
    _userNameAttr: str = ''

    def initialize(self, values: typing.Optional[typing.Dict[str, typing.Any]]) -> None:
        if values:
            self._host = values['host']
            self._port = values['port']
            self._ssl = gui.strToBool(values['ssl'])
            self._username = values['username']
            self._password = values['password']
            self._timeout = values['timeout']
            self._ldapBase = values['ldapBase']
            self._userClass = values['userClass']
            self._groupClass = values['groupClass']
            self._userIdAttr = values['userIdAttr']
            self._groupIdAttr = values['groupIdAttr']
            self._memberAttr = values['memberAttr']
            self._userNameAttr = values['userNameAttr'].replace(
                ' ', ''
            )  # Removes white spaces

    def valuesDict(self) -> gui.ValuesDictType:
        return {
            'host': self._host,
            'port': self._port,
            'ssl': gui.boolToStr(self._ssl),
            'username': self._username,
            'password': self._password,
            'timeout': self._timeout,
            'ldapBase': self._ldapBase,
            'userClass': self._userClass,
            'groupClass': self._groupClass,
            'userIdAttr': self._userIdAttr,
            'groupIdAttr': self._groupIdAttr,
            'memberAttr': self._memberAttr,
            'userNameAttr': self._userNameAttr,
        }

    def marshal(self) -> bytes:
        return '\t'.join(
            [
                'v1',
                self._host,
                self._port,
                gui.boolToStr(self._ssl),
                self._username,
                self._password,
                self._timeout,
                self._ldapBase,
                self._userClass,
                self._groupClass,
                self._userIdAttr,
                self._groupIdAttr,
                self._memberAttr,
                self._userNameAttr,
            ]
        ).encode('utf8')

    def unmarshal(self, data: bytes):
        vals = data.decode('utf8').split('\t')
        if vals[0] == 'v1':
            logger.debug("Data: %s", vals[1:])
            (
                self._host,
                self._port,
                ssl,
                self._username,
                self._password,
                self._timeout,
                self._ldapBase,
                self._userClass,
                self._groupClass,
                self._userIdAttr,
                self._groupIdAttr,
                self._memberAttr,
                self._userNameAttr,
            ) = vals[1:]
            self._ssl = gui.strToBool(ssl)

    def __connection(
        self,
        username: typing.Optional[str] = None,
        password: typing.Optional[str] = None,
    ):
        """
        Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.
        @return: Connection established
        @raise exception: If connection could not be established
        """
        if self._connection is None:  # We want this method also to check credentials
            self._connection = ldaputil.connection(
                self._username,
                self._password,
                self._host,
                port=int(self._port),
                ssl=self._ssl,
                timeout=int(self._timeout),
                debug=False,
            )

        return self._connection

    def __connectAs(self, username: str, password: str) -> typing.Any:
        return ldaputil.connection(
            username,
            password,
            self._host,
            port=int(self._port),
            ssl=self._ssl,
            timeout=int(self._timeout),
            debug=False,
        )

    def __getUser(self, username: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searchs for the username and returns its LDAP entry
        @param username: username to search, using user provided parameters at configuration to map search entries.
        @return: None if username is not found, an dictionary of LDAP entry attributes if found.
        @note: Active directory users contains the groups it belongs to in "memberOf" attribute
        """
        return ldaputil.getFirst(
            con=self.__connection(),
            base=self._ldapBase,
            objectClass=self._userClass,
            field=self._userIdAttr,
            value=username,
            attributes=[i for i in self._userNameAttr.split(',') + [self._userIdAttr]],
            sizeLimit=LDAP_RESULT_LIMIT,
        )

    def __getGroup(self, groupName: str) -> typing.Optional[ldaputil.LDAPResultType]:
        """
        Searchs for the groupName and returns its LDAP entry
        @param groupName: group name to search, using user provided parameters at configuration to map search entries.
        @return: None if group name is not found, an dictionary of LDAP entry attributes if found.
        """
        return ldaputil.getFirst(
            con=self.__connection(),
            base=self._ldapBase,
            objectClass=self._groupClass,
            field=self._groupIdAttr,
            value=groupName,
            attributes=[self._memberAttr],
            sizeLimit=LDAP_RESULT_LIMIT,
        )

    def __getGroups(self, user: ldaputil.LDAPResultType):
        try:
            groups: typing.List[str] = []

            filter_ = '(&(objectClass=%s)(|(%s=%s)(%s=%s)))' % (
                self._groupClass,
                self._memberAttr,
                user['_id'],
                self._memberAttr,
                user['dn'],
            )
            for d in ldaputil.getAsDict(
                con=self.__connection(),
                base=self._ldapBase,
                ldapFilter=filter_,
                attrList=[self._groupIdAttr],
                sizeLimit=10 * LDAP_RESULT_LIMIT,
            ):
                if self._groupIdAttr in d:
                    for k in d[self._groupIdAttr]:
                        groups.append(k)

            logger.debug('Groups: %s', groups)
            return groups

        except Exception:
            logger.exception('Exception at __getGroups')
            return []

    def __getUserRealName(self, usr: ldaputil.LDAPResultType) -> str:
        '''
        Tries to extract the real name for this user. Will return all atttributes (joint)
        specified in _userNameAttr (comma separated).
        '''
        return ' '.join(
            [
                ' '.join((str(k) for k in usr.get(id_, '')))
                if isinstance(usr.get(id_), list)
                else str(usr.get(id_, ''))
                for id_ in self._userNameAttr.split(',')
            ]
        ).strip()

    def authenticate(
        self, username: str, credentials: str, groupsManager: 'auths.GroupsManager', request: 'ExtendedHttpRequest'
    ) -> auths.AuthenticationResult:
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
            user = self.__getUser(username)

            if user is None:
                authLogLogin(
                    request, self.dbAuthenticator(), username, 'Invalid user'
                )
                return auths.FAILED_AUTH

            try:
                # Let's see first if it credentials are fine
                self.__connectAs(
                    user['dn'], credentials
                )  # Will raise an exception if it can't connect
            except:
                authLogLogin(
                    request, self.dbAuthenticator(), username, 'Invalid password'
                )
                return auths.FAILED_AUTH

            groupsManager.validate(self.__getGroups(user))

            return auths.SUCCESS_AUTH

        except Exception:
            return auths.FAILED_AUTH

    def createUser(self, usrData: typing.Dict[str, str]) -> None:
        '''
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception (AuthException) it things didn't went fine
        '''
        res = self.__getUser(usrData['name'])
        if res is None:
            raise auths.exceptions.AuthenticatorException(_('Username not found'))
        # Fills back realName field
        usrData['real_name'] = self.__getUserRealName(res)

    def getRealName(self, username: str) -> str:
        '''
        Tries to get the real name of an user
        '''
        res = self.__getUser(username)
        if res is None:
            return username
        return self.__getUserRealName(res)

    def modifyUser(self, usrData: typing.Dict[str, str]) -> None:
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        Modify user has no reason on external sources, so it will never be used (probably)
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception it things don't goes fine
        '''
        return self.createUser(usrData)

    def createGroup(self, groupData: typing.Dict[str, str]) -> None:
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has its own groups and, at most, it can check if it exists on external source before accepting it
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @params groupData: a dict that has, at least, name, comments and active
        @return:  Raises an exception it things don't goes fine
        '''
        res = self.__getGroup(groupData['name'])
        if res is None:
            raise auths.exceptions.AuthenticatorException(_('Group not found'))

    def getGroups(self, username: str, groupsManager: 'auths.GroupsManager'):
        '''
        Looks for the real groups to which the specified user belongs
        Updates groups manager with valid groups
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        '''
        user = self.__getUser(username)
        if user is None:
            raise auths.exceptions.AuthenticatorException(_('Username not found'))
        groupsManager.validate(self.__getGroups(user))

    def searchUsers(self, pattern: str) -> typing.Iterable[typing.Dict[str, str]]:
        try:
            res = []
            for r in ldaputil.getAsDict(
                con=self.__connection(),
                base=self._ldapBase,
                ldapFilter='(&(objectClass=%s)(%s=%s*))'
                % (self._userClass, self._userIdAttr, pattern),
                attrList=[self._userIdAttr, self._userNameAttr],
                sizeLimit=LDAP_RESULT_LIMIT,
            ):
                res.append(
                    {
                        'id': r[self._userIdAttr][0],  # Ignore @...
                        'name': self.__getUserRealName(r),
                    }
                )

            return res
        except Exception:
            logger.exception("Exception: ")
            raise auths.exceptions.AuthenticatorException(
                _('Too many results, be more specific')
            )

    def searchGroups(self, pattern: str) -> typing.Iterable[typing.Dict[str, str]]:
        try:
            res = []
            for r in ldaputil.getAsDict(
                con=self.__connection(),
                base=self._ldapBase,
                ldapFilter='(&(objectClass=%s)(%s=%s*))'
                % (self._groupClass, self._groupIdAttr, pattern),
                attrList=[self._groupIdAttr, 'memberOf', 'description'],
                sizeLimit=LDAP_RESULT_LIMIT,
            ):
                res.append({'id': r[self._groupIdAttr][0], 'name': r['description'][0]})

            return res
        except Exception:
            logger.exception("Exception: ")
            raise auths.exceptions.AuthenticatorException(
                _('Too many results, be more specific')
            )

    @staticmethod
    def test(env, data) -> typing.List[typing.Any]:
        try:
            auth = SimpleLDAPAuthenticator(None, env, data)  # type: ignore
            return auth.testConnection()
        except Exception as e:
            logger.error("Exception found testing Simple LDAP auth: %s", e)
            return [False, "Error testing connection"]

    def testConnection(
        self,
    ) -> typing.List[
        typing.Any
    ]:  # pylint: disable=too-many-return-statements,too-many-branches
        try:
            con = self.__connection()
        except Exception as e:
            return [False, str(e)]

        try:
            con.search_s(base=self._ldapBase, scope=ldap.SCOPE_BASE)  # type: ignore  # SCOPE.. exists on LDAP after load
        except Exception:
            return [False, _('Ldap search base is incorrect')]

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(objectClass=%s)' % self._userClass, sizelimit=1)) == 1:  # type: ignore  # SCOPE.. exists on LDAP after load
                raise Exception()
            return [
                False,
                _(
                    'Ldap user class seems to be incorrect (no user found by that class)'
                ),
            ]
        except Exception as e:
            # If found 1 or more, all right
            pass

        try:
            if (
                len(
                    con.search_ext_s(
                        base=self._ldapBase,
                        scope=ldap.SCOPE_SUBTREE,  # type: ignore  # SCOPE.. exists on LDAP after load
                        filterstr='(objectClass=%s)' % self._groupClass,
                        sizelimit=1,
                    )
                )
                == 1
            ):
                raise Exception()
            return [
                False,
                _(
                    'Ldap group class seems to be incorrect (no group found by that class)'
                ),
            ]
        except Exception as e:
            # If found 1 or more, all right
            pass

        try:
            if (
                len(
                    con.search_ext_s(
                        base=self._ldapBase,
                        scope=ldap.SCOPE_SUBTREE,  # type: ignore  # SCOPE.. exists on LDAP after load
                        filterstr='(%s=*)' % self._userIdAttr,
                        sizelimit=1,
                    )
                )
                == 1
            ):
                raise Exception()
            return [
                False,
                _(
                    'Ldap user id attribute seems to be incorrect (no user found by that attribute)'
                ),
            ]
        except Exception as e:
            # If found 1 or more, all right
            pass

        try:
            if (
                len(
                    con.search_ext_s(
                        base=self._ldapBase,
                        scope=ldap.SCOPE_SUBTREE,  # type: ignore  # SCOPE.. exists on LDAP after load
                        filterstr='(%s=*)' % self._groupIdAttr,
                        sizelimit=1,
                    )
                )
                == 1
            ):
                raise Exception()
            return [
                False,
                _(
                    'Ldap group id attribute seems to be incorrect (no group found by that attribute)'
                ),
            ]
        except Exception as e:
            # If found 1 or more, all right
            pass

        # Now test objectclass and attribute of users
        try:
            if (
                len(
                    con.search_ext_s(
                        base=self._ldapBase,
                        scope=ldap.SCOPE_SUBTREE,  # type: ignore  # SCOPE.. exists on LDAP after load
                        filterstr='(&(objectClass=%s)(%s=*))'
                        % (self._userClass, self._userIdAttr),
                        sizelimit=1,
                    )
                )
                == 1
            ):
                raise Exception()
            return [
                False,
                _(
                    'Ldap user class or user id attr is probably wrong (can\'t find any user with both conditions)'
                ),
            ]
        except Exception as e:
            # If found 1 or more, all right
            pass

        # And group part, with membership
        try:
            res = con.search_ext_s(
                base=self._ldapBase,
                scope=ldap.SCOPE_SUBTREE,  # type: ignore  # SCOPE.. exists on LDAP after load
                filterstr='(&(objectClass=%s)(%s=*))'
                % (self._groupClass, self._groupIdAttr),
                attrlist=[self._memberAttr],
            )
            if not res:
                raise Exception(
                    _(
                        'Ldap group class or group id attr is probably wrong (can\'t find any group with both conditions)'
                    )
                )
            ok = False
            for r in res:
                if self._memberAttr in r[1]:
                    ok = True
                    break
            if ok is False:
                raise Exception(
                    _('Can\'t locate any group with the membership attribute specified')
                )
        except Exception as e:
            return [False, str(e)]

        return [
            True,
            _("Connection params seem correct, test was succesfully executed"),
        ]

    def __str__(self):
        return "Ldap Auth: {0}:{1}@{2}:{3}, base = {4}, userClass = {5}, groupClass = {6}, userIdAttr = {7}, groupIdAttr = {8}, memberAttr = {9}, userName attr = {10}".format(
            self._username,
            self._password,
            self._host,
            self._port,
            self._ldapBase,
            self._userClass,
            self._groupClass,
            self._userIdAttr,
            self._groupIdAttr,
            self._memberAttr,
            self._userNameAttr,
        )
