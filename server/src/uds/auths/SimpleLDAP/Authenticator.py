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

from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core.auths import Authenticator
from uds.core.auths.Exceptions import AuthenticatorException

import ldap.filter
import ldap
import logging
import six

__updated__ = '2015-01-15'

logger = logging.getLogger(__name__)

LDAP_RESULT_LIMIT = 50


class SimpleLDAPAuthenticator(Authenticator):

    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('Ldap Server IP or Hostname'), required=True)
    port = gui.NumericField(length=5, label=_('Port'), defvalue='389', order=2, tooltip=_('Ldap port (389 for non ssl, 636 for ssl normally'), required=True)
    ssl = gui.CheckBoxField(label=_('Use SSL'), order=3, tooltip=_('If checked, will use a ssl connection to ldap (if port is 389, will use in fact port 636)'))
    username = gui.TextField(length=64, label=_('Ldap User'), order=4, tooltip=_('Username with read privileges on the base selected'), required=True)
    password = gui.PasswordField(lenth=32, label=_('Password'), order=5, tooltip=_('Password of the ldap user'), required=True)
    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=6, tooltip=_('Timeout in seconds of connection to LDAP'), required=True)
    ldapBase = gui.TextField(length=64, label=_('Base'), order=7, tooltip=_('Common search base (used for "users" and "groups"'), required=True)
    userClass = gui.TextField(length=64, label=_('User class'), defvalue='posixAccount', order=8, tooltip=_('Class for LDAP users (normally posixAccount)'), required=True)
    userIdAttr = gui.TextField(length=64, label=_('User Id Attr'), defvalue='uid', order=9, tooltip=_('Attribute that contains the user id'), required=True)
    userNameAttr = gui.TextField(length=64, label=_('User Name Attr'), defvalue='uid', order=10, tooltip=_('Attributes that contains the user name (list of comma separated values)'), required=True)
    groupClass = gui.TextField(length=64, label=_('Group class'), defvalue='posixGroup', order=11, tooltip=_('Class for LDAP groups (normally poxisGroup)'), required=True)
    groupIdAttr = gui.TextField(length=64, label=_('Group Id Attr'), defvalue='cn', order=12, tooltip=_('Attribute that contains the group id'), required=True)
    memberAttr = gui.TextField(length=64, label=_('Group membership attr'), defvalue='memberUid', order=13, tooltip=_('Attribute of the group that contains the users belonging to it'), required=True)

    typeName = _('SimpleLDAP Authenticator')
    typeType = 'SimpleLdapAuthenticator'
    typeDescription = _('Simple LDAP authenticator')
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

    def __init__(self, dbAuth, environment, values=None):
        super(SimpleLDAPAuthenticator, self).__init__(dbAuth, environment, values)
        if values is not None:
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
            self._userNameAttr = values['userNameAttr'].replace(' ', '')  # Removes white spaces
        else:
            self._host = None
            self._port = None
            self._ssl = None
            self._username = None
            self._password = None
            self._timeout = None
            self._ldapBase = None
            self._userClass = None
            self._groupClass = None
            self._userIdAttr = None
            self._groupIdAttr = None
            self._memberAttr = None
            self._userNameAttr = None
        self._connection = None

    def valuesDict(self):
        return {
            'host': self._host, 'port': self._port, 'ssl': gui.boolToStr(self._ssl),
            'username': self._username, 'password': self._password, 'timeout': self._timeout,
            'ldapBase': self._ldapBase, 'userClass': self._userClass, 'groupClass': self._groupClass,
            'userIdAttr': self._userIdAttr, 'groupIdAttr': self._groupIdAttr, 'memberAttr': self._memberAttr,
            'userNameAttr': self._userNameAttr
        }

    def __str__(self):
        return "Ldap Auth: {0}:{1}@{2}:{3}, base = {4}, userClass = {5}, groupClass = {6}, userIdAttr = {7}, groupIdAttr = {8}, memberAttr = {9}, userName attr = {10}".format(
            self._username, self._password, self._host, self._port, self._ldapBase, self._userClass, self._groupClass, self._userIdAttr, self._groupIdAttr, self._memberAttr,
            self._userNameAttr)

    def marshal(self):
        return '\t'.join(['v1',
                          self._host, self._port, gui.boolToStr(self._ssl), self._username, self._password, self._timeout,
                          self._ldapBase, self._userClass, self._groupClass, self._userIdAttr, self._groupIdAttr, self._memberAttr, self._userNameAttr])

    def unmarshal(self, str_):
        data = str_.split('\t')
        if data[0] == 'v1':
            logger.debug("Data: {0}".format(data[1:]))
            self._host, self._port, self._ssl, self._username, self._password, self._timeout, self._ldapBase, self._userClass, self._groupClass, self._userIdAttr, self._groupIdAttr, self._memberAttr, self._userNameAttr = data[1:]
            self._ssl = gui.strToBool(self._ssl)

    def __connection(self, username=None, password=None):
        if self._connection is None or username is not None:  # We want this method also to check credentials
            if isinstance(username, six.text_type):
                username = username.encode('utf8')
            if isinstance(password, six.text_type):
                password = password.encode('utf8')
            l = None
            cache = False
            try:
                # ldap.set_option(ldap.OPT_DEBUG_LEVEL, 9)
                ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
                schema = self._ssl and 'ldaps' or 'ldap'
                port = self._port != '389' and ':' + self._port or ''
                uri = "%s://%s%s" % (schema, self._host, port)
                logger.debug('Ldap uri: {0}'.format(uri))
                l = ldap.initialize(uri=uri)
                l.network_timeout = l.timeout = int(self._timeout)
                l.protocol_version = ldap.VERSION3

                if username is None:
                    cache = True
                    username = self._username
                    password = self._password

                l.simple_bind_s(who=username, cred=password)
            except ldap.LDAPError, e:
                str_ = _('Ldap connection error: ')
                if type(e.message) == dict:
                    str_ += 'info' in e.message and e.message['info'] + ',' or ''
                    str_ += 'desc' in e.message and e.message['desc'] or ''
                else:
                    str_ += str_(e)
                raise Exception(str_)
            if cache is True:
                self._connection = l
            else:
                return l  # Do not cache nor overwrite "global" connection
        return self._connection

    def __getUser(self, username):
        try:
            con = self.__connection()
            filter_ = '(&(objectClass=%s)(%s=%s))' % (self._userClass, self._userIdAttr, ldap.filter.escape_filter_chars(username, 0))
            attrlist = [i.encode('utf-8') for i in  self._userNameAttr.split(',') + [self._userIdAttr]]
            logger.debug('Getuser filter_: {0}, attr list: {1}'.format(filter_, attrlist))
            res = con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE,
                             filterstr=filter_, attrlist=attrlist, sizelimit=LDAP_RESULT_LIMIT)[0]
            usr = dict((k, '') for k in attrlist)
            usr.update(res[1])
            usr.update({'dn': res[0], '_id': username})
            logger.debug('Usr: {0}'.format(usr))
            return usr
        except Exception:
            logger.exception('Exception:')
            return None

    def __getGroup(self, groupName):
        try:
            con = self.__connection()
            filter_ = '(&(objectClass=%s)(%s=%s))' % (self._groupClass, self._groupIdAttr, groupName)
            attrlist = [self._memberAttr.encode('utf-8')]
            logger.debug('Getgroup filter_: {0}, attr list {1}'.format(filter_, attrlist))
            res = con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE,
                                   filterstr=filter_, attrlist=attrlist, sizelimit=LDAP_RESULT_LIMIT * 10)[0]
            grp = dict((k, ['']) for k in attrlist)
            grp.update(res[1])
            grp.update({'dn': res[0], '_id': groupName})
            logger.debug('Group: {0}'.format(grp))
            return grp
        except Exception:
            logger.exception('Exception:')
            return None

    def __getGroups(self, usr):
        try:
            con = self.__connection()
            filter_ = '(&(objectClass=%s)(|(%s=%s)(%s=%s)))' % (self._groupClass, self._memberAttr, usr['_id'], self._memberAttr, usr['dn'])
            logger.debug('Filter: {0}'.format(filter_))
            res = con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr=filter_, attrlist=[self._groupIdAttr.encode('utf8')],
                                   sizelimit=LDAP_RESULT_LIMIT * 10)
            groups = {}
            for g in res:
                v = g[1][self._groupIdAttr]
                if type(v) is not list:
                    v = [v]
                for gg in v:
                    groups[str(gg)] = g[0]
            logger.debug('Groups: {0}'.format(groups))
            return groups

        except Exception:
            logger.exception('Exception at __getGroups')
            return {}

    def __getUserRealName(self, usr):
        '''
        Tries to extract the real name for this user. Will return all atttributes (joint)
        specified in _userNameAttr (comma separated).
        '''
        return ' '.join([(type(usr.get(id_, '')) is list and ' '.join((str(k) for k in usr.get(id_, ''))) or str(usr.get(id_, ''))) for id_ in self._userNameAttr.split(',')]).strip()

    def authenticate(self, username, credentials, groupsManager):
        '''
        Must authenticate the user.
        We can have to different situations here:
           1.- The authenticator is external source, what means that users may be unknown to system before callig this
           2.- The authenticator isn't external source, what means that users have been manually added to system and are known before this call
        We receive the username, the credentials used (normally password, but can be a public key or something related to pk) and a group manager.
        The group manager is responsible for letting know the authenticator which groups we currently has active.
        @see: uds.core.auths.GroupsManager
        '''
        try:
            # Locate the user at LDAP
            usr = self.__getUser(username)

            if usr is None:
                return False

            # Let's see first if it credentials are fine
            self.__connection(usr['dn'], credentials)  # Will raise an exception if it can't connect

            groupsManager.validate(self.__getGroups(usr).keys())

            return True

        except Exception:
            return False

    def createUser(self, usrData):
        '''
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception (AuthException) it things didn't went fine
        '''
        res = self.__getUser(usrData['name'])
        if res is None:
            raise AuthenticatorException(_('Username not found'))
        # Fills back realName field
        usrData['real_name'] = self.__getUserRealName(res)

    def getRealName(self, username):
        '''
        Tries to get the real name of an user
        '''
        res = self.__getUser(username)
        if res is None:
            return username
        return self.__getUserRealName(res)

    def modifyUser(self, usrData):
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        Modify user has no reason on external sources, so it will never be used (probably)
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @param usrData: Contains data received from user directly, that is, a dictionary with at least: name, realName, comments, state & password
        @return:  Raises an exception it things don't goes fine
        '''
        return self.createUser(usrData)

    def createGroup(self, groupData):
        '''
        We must override this method in authenticators not based on external sources (i.e. database users, text file users, etc..)
        External sources already has its own groups and, at most, it can check if it exists on external source before accepting it
        Groups are only used in case of internal users (non external sources) that must know to witch groups this user belongs to
        @params groupData: a dict that has, at least, name, comments and active
        @return:  Raises an exception it things don't goes fine
        '''
        res = self.__getGroup(groupData['name'])
        if res is None:
            raise AuthenticatorException(_('Group not found'))

    def getGroups(self, username, groupsManager):
        '''
        Looks for the real groups to which the specified user belongs
        Updates groups manager with valid groups
        Remember to override it in derived authentication if needed (external auths will need this, for internal authenticators this is never used)
        '''
        user = self.__getUser(username)
        if user is None:
            raise AuthenticatorException(_('Username not found'))
        groupsManager.validate(self.__getGroups(user).keys())

    def searchUsers(self, pattern):
        try:
            con = self.__connection()
            res = []
            for r in con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(&(objectClass=%s)(%s=%s*))' % (self._userClass, self._userIdAttr, pattern), sizelimit=LDAP_RESULT_LIMIT):
                usrId = r[1].get(self._userIdAttr, '')
                usrId = type(usrId) == list and usrId[0] or usrId
                res.append({
                    'id': usrId,
                    'name': self.__getUserRealName(r[1])
                })
            return res
        except Exception:
            logger.exception("Exception: ")
            raise AuthenticatorException(_('Too many results, be more specific'))

    def searchGroups(self, pattern):
        try:
            con = self.__connection()
            res = []
            for r in con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(&(objectClass=%s)(%s=%s*))' % (self._groupClass, self._groupIdAttr, pattern), sizelimit=LDAP_RESULT_LIMIT):
                grpId = r[1].get(self._groupIdAttr, '')
                grpId = type(grpId) == list and grpId[0] or grpId
                res.append({
                    'id': grpId,
                    'name': grpId
                })
            return res
        except Exception:
            logger.exception("Exception: ")
            raise AuthenticatorException(_('Too many results, be more specific'))

    @staticmethod
    def test(env, data):
        try:
            auth = SimpleLDAPAuthenticator(None, env, data)
            return auth.testConnection()
        except Exception, e:
            logger.error("Exception found testing Simple LDAP auth {0}: {1}".format(e.__class__, e))
            return [False, "Error testing connection"]

    def testConnection(self):
        try:
            con = self.__connection()
        except Exception, e:
            return [False, str(e)]

        try:
            con.search_s(base=self._ldapBase, scope=ldap.SCOPE_BASE)
        except Exception:
            return [False, _('Ldap search base is incorrect')]

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(objectClass=%s)' % self._userClass, sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap user class seems to be incorrect (no user found by that class)')]
        except Exception, e:
            # If found 1 or more, all right
            pass

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(objectClass=%s)' % self._groupClass, sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap group class seems to be incorrect (no group found by that class)')]
        except Exception, e:
            # If found 1 or more, all right
            pass

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(%s=*)' % self._userIdAttr, sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap user id attribute seems to be incorrect (no user found by that attribute)')]
        except Exception, e:
            # If found 1 or more, all right
            pass

        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(%s=*)' % self._groupIdAttr, sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap group id attribute seems to be incorrect (no group found by that attribute)')]
        except Exception, e:
            # If found 1 or more, all right
            pass

        # Now test objectclass and attribute of users
        try:
            if len(con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(&(objectClass=%s)(%s=*))' % (self._userClass, self._userIdAttr), sizelimit=1)) == 1:
                raise Exception()
            return [False, _('Ldap user class or user id attr is probably wrong (can\'t find any user with both conditions)')]
        except Exception, e:
            # If found 1 or more, all right
            pass

        # And group part, with membership
        try:
            res = con.search_ext_s(base=self._ldapBase, scope=ldap.SCOPE_SUBTREE, filterstr='(&(objectClass=%s)(%s=*))' % (self._groupClass, self._groupIdAttr), attrlist=[self._memberAttr.encode('utf-8')])
            if len(res) == 0:
                raise Exception(_('Ldap group class or group id attr is probably wrong (can\'t find any group with both conditions)'))
            ok = False
            for r in res:
                if self._memberAttr in  r[1]:
                    ok = True
                    break
            if ok is False:
                raise Exception(_('Can\'t locate any group with the membership attribute specified'))
        except Exception, e:
            return [False, str(e)]

        return [True, _("Connection params seem correct, test was succesfully executed")]
