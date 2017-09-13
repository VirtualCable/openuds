# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.ui.UserInterface import gui
from uds.core.managers.CryptoManager import CryptoManager
from uds.core import osmanagers
from WindowsOsManager import WindowsOsManager
from uds.core.util import log
import dns.resolver
import ldap
import six

import logging

logger = logging.getLogger(__name__)


class WinDomainOsManager(WindowsOsManager):
    typeName = _('Windows Domain OS Manager')
    typeType = 'WinDomainManager'
    typeDescription = _('Os Manager to control windows machines with domain.')
    iconFile = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    domain = gui.TextField(length=64, label=_('Domain'), order=1, tooltip=_('Domain to join machines to (use FQDN form, Netbios name not supported for most operations)'), required=True)
    account = gui.TextField(length=64, label=_('Account'), order=2, tooltip=_('Account with rights to add machines to domain'), required=True)
    password = gui.PasswordField(length=64, label=_('Password'), order=3, tooltip=_('Password of the account'), required=True)
    ou = gui.TextField(length=64, label=_('OU'), order=4, tooltip=_('Organizational unit where to add machines in domain (check it before using it). i.e.: ou=My Machines,dc=mydomain,dc=local'))
    grp = gui.TextField(length=64, label=_('Machine Group'), order=7, tooltip=_('Group to which add machines on creation. If empty, no group will be used. (experimental)'), tab=_('Advanced'))
    serverHint = gui.TextField(length=64, label=_('Server Hint'), order=8, tooltip=_('In case of several AD servers, which one is prefered for first access'), tab=_('Advanced'))
    # Inherits base "onLogout"
    onLogout = WindowsOsManager.onLogout
    idle = WindowsOsManager.idle

    def __init__(self, environment, values):
        super(WinDomainOsManager, self).__init__(environment, values)
        if values is not None:
            if values['domain'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide a domain!'))
            # if values['domain'].find('.') == -1:
            #    raise osmanagers.OSManager.ValidationException(_('Must provide domain in FQDN'))
            if values['account'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide an account to add machines to domain!'))
            if values['account'].find('\\') != -1:
                raise osmanagers.OSManager.ValidationException(_('DOM\\USER form is not allowed!'))
            if values['password'] == '':
                raise osmanagers.OSManager.ValidationException(_('Must provide a password for the account!'))
            self._domain = values['domain']
            self._ou = values['ou'].strip()
            self._account = values['account']
            self._password = values['password']
            self._group = values['grp'].strip()
            self._serverHint = values['serverHint'].strip()
        else:
            self._domain = ""
            self._ou = ""
            self._account = ""
            self._password = ""
            self._group = ""
            self._serverHint = ""

        # self._ou = self._ou.replace(' ', ''), do not remove spaces
        if self._domain != '' and self._ou != '':
            lpath = 'dc=' + ',dc='.join((s.lower() for s in self._domain.split('.')))
            if self._ou.lower().find(lpath) == -1:
                self._ou += ',' + lpath

    def __getLdapError(self, e):
        logger.debug('Ldap Error: {0} {1}'.format(e, e.message))
        _str = ''
        if type(e.message) == dict:
            # _str += e.message.has_key('info') and e.message['info'] + ',' or ''
            _str += e.message.get('desc', '')
        else:
            _str += str(e)
        return _str

    def __getServerList(self):
        if self._serverHint != '':
            yield (self._serverHint, 389)

        for server in reversed(sorted(dns.resolver.query('_ldap._tcp.' + self._domain, 'SRV'), key=lambda i: i.priority * 10000 + i.weight)):
            yield (six.text_type(server.target)[:-1], server.port)

    def __connectLdap(self, servers=None):
        '''
        Tries to connect to LDAP
        Raises an exception if not found:
            dns.resolver.NXDOMAIN
            ldap.LDAPError
        '''
        if servers is None:
            servers = self.__getServerList()

        for server in servers:

            _str = ''

            try:
                uri = "%s://%s:%d" % ('ldap', server[0], server[1])
                logger.debug('URI: {0}'.format(uri))

                ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # Disable certificate check
                l = ldap.initialize(uri=uri)
                l.set_option(ldap.OPT_REFERRALS, 0)
                l.network_timeout = l.timeout = 5
                l.protocol_version = ldap.VERSION3

                account = self._account
                if account.find('@') == -1:
                    account += '@' + self._domain

                logger.debug('Account data: {0}, {1}, {2}, {3}'.format(self._account, self._domain, account, self._password))

                l.simple_bind_s(who=account, cred=self._password)

                return l
            except ldap.LDAPError as e:
                _str = self.__getLdapError(e)

        raise ldap.LDAPError(_str)

    def __getGroup(self, l):
        base = ','.join(['DC=' + i for i in self._domain.split('.')])
        group = self._group.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')

        res = l.search_ext_s(base=base, scope=ldap.SCOPE_SUBTREE, filterstr="(&(objectClass=group)(|(cn={0})(sAMAccountName={0})))".format(group), attrlist=[b'dn'])
        if res[0] is None:
            return None

        return res[0][0]  # Returns the DN

    def __getMachine(self, l, machineName):
        if self._ou:
            ou = self._ou
        else:
            ou = ','.join(['DC=' + i for i in self._domain.split('.')])

        fltr = '(&(objectClass=computer)(sAMAccountName={}$))'.format(machineName)
        res = l.search_ext_s(base=ou, scope=ldap.SCOPE_SUBTREE, filterstr=fltr, attrlist=[b'dn'])
        if res[0] is None:
            return None

        return res[0][0]  # Returns the DN

    def readyReceived(self, userService, data):
        # No group to add
        if self._group == '':
            return

        if not '.' in self._domain:
            logger.info('Adding to a group for a non FQDN domain is not supported')
            return

        # The machine is on a AD for sure, and maybe they are not already sync
        servers = list(self.__getServerList())

        error = None
        for s in servers:
            try:
                l = self.__connectLdap(servers=(s,))

                machine = self.__getMachine(l, userService.friendly_name)
                group = self.__getGroup(l)
                l.modify_s(group, ((ldap.MOD_ADD, 'member', machine),))
                error = None
                break
            except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
                logger.warn('Could not find _ldap._tcp.' + self._domain)
                log.doLog(userService, log.WARN, "Could not remove machine from domain (_ldap._tcp.{0} not found)".format(self._domain), log.OSMANAGER)
            except ldap.ALREADY_EXISTS:
                # Already added this machine to this group, pass
                error = None
                break
            except ldap.LDAPError:
                logger.exception('Ldap Exception caught')
                error = "Could not remove machine from domain (invalid credentials for {0})".format(self._account)
            except Exception as e:
                error = "Could not add machine {} to group {}: {}".format(userService.friendly_name, self._group, e)
                # logger.exception('Ldap Exception caught')

        if error is not None:
            log.doLog(userService, log.WARN, error, log.OSMANAGER)
            logger.error(error)

    def release(self, service):
        '''
        service is a db user service object
        '''
        super(WinDomainOsManager, self).release(service)

        if not '.' in self._domain:
            logger.info('Releasing from a not FQDN domain is not supported')
            return

        try:
            l = self.__connectLdap()
        except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
            logger.warn('Could not find _ldap._tcp.' + self._domain)
            log.doLog(service, log.WARN, "Could not remove machine from domain (_ldap._tcp.{0} not found)".format(self._domain), log.OSMANAGER)
        except ldap.LDAPError:
            logger.exception('Ldap Exception caught')
            log.doLog(service, log.WARN, "Could not remove machine from domain (invalid credentials for {0})".format(self._account), log.OSMANAGER)

        try:
            res = self.__getMachine(l, service.friendly_name)
            if res is None:
                raise Exception('Machine {} not found on AD (permissions?)'.format(service.friendly_name))
            l.delete_s(res)  # Remove by DN, SYNC
        except IndexError:
            logger.error('Error deleting {} from BASE {}'.format(service.friendly_name, ou))
        except Exception:
            logger.exception('Deleting from AD: ')

    def check(self):
        try:
            l = self.__connectLdap()
        except ldap.LDAPError as e:
            return _('Check error: {0}').format(self.__getLdapError(e))
        except dns.resolver.NXDOMAIN:
            return [True, _('Could not find server parameters (_ldap._tcp.{0} can\'t be resolved)').format(self._domain)]
        except Exception as e:
            logger.exception('Exception ')
            return [False, str(e)]

        try:
            l.search_st(self._ou, ldap.SCOPE_BASE)
        except ldap.LDAPError as e:
            return _('Check error: {0}').format(self.__getLdapError(e))

        # Group
        if self._group != '':
            if self.__getGroup(l) is None:
                return _('Check Error: group "{}" not found (using "cn" to locate it)').format(self._group)


        return _('Server check was successful')

    @staticmethod
    def test(env, data):
        logger.debug('Test invoked')
        try:
            wd = WinDomainOsManager(env, data)
            logger.debug(wd)
            try:
                l = wd.__connectLdap()
            except ldap.LDAPError as e:
                return [False, _('Could not access AD using LDAP ({0})').format(wd.__getLdapError(e))]

            ou = wd._ou
            if ou == '':
                ou = 'cn=Computers,dc=' + ',dc='.join(wd._domain.split('.'))

            logger.debug('Checking {0} with ou {1}'.format(wd._domain, ou))
            r = l.search_st(ou, ldap.SCOPE_BASE)
            logger.debug('Result of search: {0}'.format(r))

        except ldap.LDAPError:
            if wd._ou == '':
                return [False, _('The default path {0} for computers was not found!!!').format(ou)]
            else:
                return [False, _('The ou path {0} was not found!!!').format(ou)]
        except dns.resolver.NXDOMAIN:
            return [True, _('Could not check parameters (_ldap._tcp.{0} can\'r be resolved)').format(wd._domain)]
        except Exception as e:
            logger.exception('Exception ')
            return [False, str(e)]

        return [True, _("All parameters seem to work fine.")]

    def infoVal(self, service):
        return 'domain:{0}\t{1}\t{2}\t{3}\t{4}'.format(self.getName(service), self._domain, self._ou, self._account, self._password)

    def infoValue(self, service):
        return 'domain\r{0}\t{1}\t{2}\t{3}\t{4}'.format(self.getName(service), self._domain, self._ou, self._account, self._password)

    def marshal(self):
        base = super(WinDomainOsManager, self).marshal()
        '''
        Serializes the os manager data so we can store it in database
        '''
        return '\t'.join(['v3', self._domain, self._ou, self._account, CryptoManager.manager().encrypt(self._password), base.encode('hex'), self._group, self._serverHint])

    def unmarshal(self, s):
        data = s.split('\t')
        if data[0] in ('v1', 'v2', 'v3'):
            self._domain = data[1]
            self._ou = data[2]
            self._account = data[3]
            self._password = CryptoManager.manager().decrypt(data[4])

        if data[0] in ('v2', 'v3'):
            self._group = data[6]
        else:
            self._group = ''

        if data[0] == 'v3':
            self._serverHint = data[7]
        else:
            self._serverHint = ''

        super(WinDomainOsManager, self).unmarshal(data[5].decode('hex'))

    def valuesDict(self):
        dct = super(WinDomainOsManager, self).valuesDict()
        dct['domain'] = self._domain
        dct['ou'] = self._ou
        dct['account'] = self._account
        dct['password'] = self._password
        dct['grp'] = self._group
        dct['serverHint'] = self._serverHint
        return dct
