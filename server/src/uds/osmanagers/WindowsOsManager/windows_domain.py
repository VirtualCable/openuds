# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
# All rights reserved.
#
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import codecs
import logging
import typing

import dns.resolver
import ldap

from django.utils.translation import ugettext_noop as _
from uds.core.ui import gui
from uds.core.managers import cryptoManager
from uds.core import osmanagers
from uds.core.util import log
from uds.core.util import ldaputil

from .windows import WindowsOsManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module
    from uds.core.environment import Environment
    from uds.models import UserService


logger = logging.getLogger(__name__)


class WinDomainOsManager(WindowsOsManager):
    typeName = _('Windows Domain OS Manager')
    typeType = 'WinDomainManager'
    typeDescription = _('Os Manager to control windows machines with domain.')
    iconFile = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    domain = gui.TextField(
        length=64,
        label=_('Domain'),
        order=1,
        tooltip=_(
            'Domain to join machines to (use FQDN form, Netbios name not supported for most operations)'
        ),
        required=True,
    )
    account = gui.TextField(
        length=64,
        label=_('Account'),
        order=2,
        tooltip=_('Account with rights to add machines to domain'),
        required=True,
    )
    password = gui.PasswordField(
        length=64,
        label=_('Password'),
        order=3,
        tooltip=_('Password of the account'),
        required=True,
    )
    ou = gui.TextField(
        length=256,
        label=_('OU'),
        order=4,
        tooltip=_(
            'Organizational unit where to add machines in domain (check it before using it). i.e.: ou=My Machines,dc=mydomain,dc=local'
        ),
    )
    grp = gui.TextField(
        length=64,
        label=_('Machine Group'),
        order=7,
        tooltip=_(
            'Group to which add machines on creation. If empty, no group will be used.'
        ),
        tab=_('Advanced'),
    )
    removeOnExit = gui.CheckBoxField(
        label=_('Machine clean'),
        order=8,
        tooltip=_(
            'If checked, UDS will try to remove the machine from the domain USING the provided credentials'
        ),
        tab=_('Advanced'),
        defvalue=gui.TRUE,
    )
    serverHint = gui.TextField(
        length=64,
        label=_('Server Hint'),
        order=9,
        tooltip=_('In case of several AD servers, which one is preferred (only used for group and account removal operations)'),
        tab=_('Advanced'),
    )
    ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=10,
        tooltip=_('If checked,  a ssl connection to Active Directory will be used'),
        tab=_('Advanced'),
        defvalue=gui.FALSE,
    )

    # Inherits base "onLogout"
    onLogout = WindowsOsManager.onLogout
    idle = WindowsOsManager.idle
    deadLine = WindowsOsManager.deadLine

    _domain: str
    _ou: str
    _account: str
    _pasword: str
    _group: str
    _serverHint: str
    _removeOnExit: str
    _ssl: str

    def __init__(self, environment: 'Environment', values: 'Module.ValuesType'):
        super().__init__(environment, values)
        if values:
            if values['domain'] == '':
                raise osmanagers.OSManager.ValidationException(
                    _('Must provide a domain!')
                )
            # if values['domain'].find('.') == -1:
            #    raise osmanagers.OSManager.ValidationException(_('Must provide domain in FQDN'))
            if values['account'] == '':
                raise osmanagers.OSManager.ValidationException(
                    _('Must provide an account to add machines to domain!')
                )
            if values['account'].find('\\') != -1:
                raise osmanagers.OSManager.ValidationException(
                    _('DOM\\USER form is not allowed!')
                )
            if values['password'] == '':
                raise osmanagers.OSManager.ValidationException(
                    _('Must provide a password for the account!')
                )
            self._domain = values['domain']
            self._ou = values['ou'].strip()
            self._account = values['account']
            self._password = values['password']
            self._group = values['grp'].strip()
            self._serverHint = values['serverHint'].strip()
            self._ssl = 'y' if values['ssl'] else 'n'
            self._removeOnExit = 'y' if values['removeOnExit'] else 'n'
        else:
            self._domain = ""
            self._ou = ""
            self._account = ""
            self._password = ""
            self._group = ""
            self._serverHint = ""
            self._removeOnExit = 'n'
            self._ssl = 'n'

        # self._ou = self._ou.replace(' ', ''), do not remove spaces
        if self._domain != '' and self._ou != '':
            lpath = 'dc=' + ',dc='.join((s.lower() for s in self._domain.split('.')))
            if self._ou.lower().find(lpath) == -1:
                self._ou += ',' + lpath

    def __getServerList(self) -> typing.Iterable[typing.Tuple[str, int]]:
        if self._serverHint != '':
            yield (self._serverHint, 389)

        for server in reversed(
            sorted(
                dns.resolver.query('_ldap._tcp.' + self._domain, 'SRV'),  # type: ignore
                key=lambda i: i.priority * 10000 + i.weight,
            )
        ):
            yield (str(server.target)[:-1], server.port)

    def __connectLdap(
        self, servers: typing.Optional[typing.Iterable[typing.Tuple[str, int]]] = None
    ) -> typing.Any:
        """
        Tries to connect to LDAP
        Raises an exception if not found:
            dns.resolver.NXDOMAIN
            ldaputil.LDAPError
        """
        if servers is None:
            servers = self.__getServerList()

        account = self._account
        if account.find('@') == -1:
            account += '@' + self._domain

        _str = "No servers found"
        # And if not possible, try using NON-SSL
        for server in servers:
            ssl = self._ssl == 'y'
            port = server[1] if not ssl else -1
            try:
                return ldaputil.connection(
                    account,
                    self._password,
                    server[0],
                    port,
                    ssl=ssl,
                    timeout=10,
                    debug=False,
                )
            except Exception as e:
                _str = 'Error: {}'.format(e)

        raise ldaputil.LDAPError(_str)

    def __getGroup(self, ldapConnection: typing.Any) -> typing.Optional[str]:
        base = ','.join(['DC=' + i for i in self._domain.split('.')])
        group = ldaputil.escape(self._group)
        obj: typing.Optional[typing.MutableMapping[str, typing.Any]]
        try:
            obj = next(
                ldaputil.getAsDict(
                    ldapConnection,
                    base,
                    "(&(objectClass=group)(|(cn={0})(sAMAccountName={0})))".format(
                        group
                    ),
                    ['dn'],
                    sizeLimit=50,
                )
            )
        except StopIteration:
            obj = None

        if obj is None:
            return None

        return obj['dn']  # Returns the DN

    def __getMachine(self, ldapConnection, machineName: str) -> typing.Optional[str]:
        # if self._ou:
        #     base = self._ou
        # else:
        base = ','.join(['DC=' + i for i in self._domain.split('.')])

        fltr = '(&(objectClass=computer)(sAMAccountName={}$))'.format(
            ldaputil.escape(machineName)
        )
        obj: typing.Optional[typing.MutableMapping[str, typing.Any]]
        try:
            obj = next(
                ldaputil.getAsDict(ldapConnection, base, fltr, ['dn'], sizeLimit=50)
            )
        except StopIteration:
            obj = None

        if obj is None:
            return None

        return obj['dn']  # Returns the DN

    def readyNotified(self, userService: 'UserService') -> None:
        # No group to add
        if self._group == '':
            return

        if '.' not in self._domain:
            logger.info('Adding to a group for a non FQDN domain is not supported')
            return

        # The machine is on a AD for sure, and maybe they are not already sync
        error: typing.Optional[str] = None
        for s in self.__getServerList():
            try:
                ldapConnection = self.__connectLdap(servers=(s,))

                machine = self.__getMachine(ldapConnection, userService.friendly_name)
                group = self.__getGroup(ldapConnection)
                # #
                # Direct LDAP operation "modify", maybe this need to be added to ldaputil? :)
                # #
                ldapConnection.modify_s(
                    group, ((ldap.MOD_ADD, 'member', [machine.encode()]),)  # type: ignore  # (valid)
                )  # @UndefinedVariable
                error = None
                break
            except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
                logger.warning('Could not find _ldap._tcp.%s', self._domain)
                log.doLog(
                    userService,
                    log.WARN,
                    "Could not remove machine from domain (_ldap._tcp.{0} not found)".format(
                        self._domain
                    ),
                    log.OSMANAGER,
                )
            except ldap.ALREADY_EXISTS:  # type: ignore  # (valid)
                # Already added this machine to this group, pass
                error = None
                break
            except ldaputil.LDAPError:
                logger.exception('Ldap Exception caught')
                error = "Could not add machine (invalid credentials? for {0})".format(
                    self._account
                )
            except Exception as e:
                error = "Could not add machine {} to group {}: {}".format(
                    userService.friendly_name, self._group, e
                )
                # logger.exception('Ldap Exception caught')

        if error:
            log.doLog(userService, log.WARN, error, log.OSMANAGER)
            logger.error(error)

    def release(self, userService: 'UserService') -> None:
        super().release(userService)

        # If no removal requested, just return
        if self._removeOnExit != 'y':
            return

        if '.' not in self._domain:
            # logger.info('Releasing from a not FQDN domain is not supported')
            log.doLog(
                userService,
                log.INFO,
                "Removing a domain machine form a non FQDN domain is not supported.",
                log.OSMANAGER,
            )
            return

        try:
            ldapConnection = self.__connectLdap()
        except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
            logger.warning('Could not find _ldap._tcp.%s', self._domain)
            log.doLog(
                userService,
                log.WARN,
                "Could not remove machine from domain (_ldap._tcp.{} not found)".format(
                    self._domain
                ),
                log.OSMANAGER,
            )
            return
        except ldaputil.LDAPError as e:
            # logger.exception('Ldap Exception caught')
            log.doLog(
                userService,
                log.WARN,
                "Could not remove machine from domain ({})".format(e),
                log.OSMANAGER,
            )
            return
        except Exception as e:
            # logger.exception('Exception caught')
            log.doLog(
                userService,
                log.WARN,
                "Could not remove machine from domain ({})".format(e),
                log.OSMANAGER,
            )
            return

        try:
            res = self.__getMachine(ldapConnection, userService.friendly_name)
            if res is None:
                raise Exception(
                    'Machine {} not found on AD (permissions?)'.format(
                        userService.friendly_name
                    )
                )
            ldaputil.recursive_delete(ldapConnection, res)
        except IndexError:
            logger.error(
                'Error deleting %s from BASE %s', userService.friendly_name, self._ou
            )
        except Exception:
            logger.exception('Deleting from AD: ')

    def check(self) -> str:
        try:
            ldapConnection = self.__connectLdap()
        except ldaputil.LDAPError as e:
            return _('Check error: {}').format(e)
        except dns.resolver.NXDOMAIN:
            return _(
                'Could not find server parameters (_ldap._tcp.{0} can\'t be resolved)'
            ).format(self._domain)
        except Exception as e:
            logger.exception('Exception ')
            return str(e)

        try:
            ldapConnection.search_st(self._ou, ldap.SCOPE_BASE)  # type: ignore  # (valid)
        except ldaputil.LDAPError as e:
            return _('Check error: {}').format(e)

        # Group
        if self._group != '':
            if self.__getGroup(ldapConnection) is None:
                return _(
                    'Check Error: group "{}" not found (using "cn" to locate it)'
                ).format(self._group)

        return _('Server check was successful')

    # pylint: disable=protected-access
    @staticmethod
    def test(
        env: 'Environment', data: typing.Dict[str, str]
    ) -> typing.List[typing.Any]:
        logger.debug('Test invoked')
        wd = WinDomainOsManager(env, data)
        logger.debug(wd)
        try:
            try:
                ldapConnection = wd.__connectLdap()
            except ldaputil.LDAPError as e:
                return [False, _('Could not access AD using LDAP ({0})').format(e)]

            ou = wd._ou
            if ou == '':
                ou = 'cn=Computers,dc=' + ',dc='.join(wd._domain.split('.'))

            logger.info('Checking %s with ou %s', wd._domain, ou)
            r = ldapConnection.search_st(ou, ldap.SCOPE_BASE)  # type: ignore  # (valid)
            logger.info('Result of search: %s', r)

        except ldaputil.LDAPError:
            if wd and not wd._ou:
                return [
                    False,
                    _('The default path {0} for computers was not found!!!').format(
                        wd._ou
                    ),
                ]
            return [False, _('The ou path {0} was not found!!!').format(wd._ou)]
        except dns.resolver.NXDOMAIN:
            return [
                True,
                _(
                    'Could not check parameters (_ldap._tcp.{0} can\'r be resolved)'
                ).format(wd._domain),
            ]
        except Exception as e:
            logger.exception('Exception ')
            return [False, str(e)]

        return [True, _("All parameters seem to work fine.")]

    def actorData(
        self, userService: 'UserService'
    ) -> typing.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename_ad',
            'name': userService.getName(),
            'ad': self._domain,
            'ou': self._ou,
            'username': self._account,
            'password': self._password,
        }

    def infoVal(self, userService: 'UserService') -> str:
        return 'domain:{0}\t{1}\t{2}\t{3}\t{4}'.format(
            self.getName(userService),
            self._domain,
            self._ou,
            self._account,
            self._password,
        )

    def infoValue(self, userService: 'UserService') -> str:
        return 'domain\r{0}\t{1}\t{2}\t{3}\t{4}'.format(
            self.getName(userService),
            self._domain,
            self._ou,
            self._account,
            self._password,
        )

    def marshal(self) -> bytes:
        """
        Serializes the os manager data so we can store it in database
        """
        base = codecs.encode(super().marshal(), 'hex').decode()
        return '\t'.join(
            [
                'v4',
                self._domain,
                self._ou,
                self._account,
                cryptoManager().encrypt(self._password),
                base,
                self._group,
                self._serverHint,
                self._ssl,
                self._removeOnExit,
            ]
        ).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        values = data.decode('utf8').split('\t')
        if values[0] in ('v1', 'v2', 'v3', 'v4'):
            self._domain = values[1]
            self._ou = values[2]
            self._account = values[3]
            self._password = cryptoManager().decrypt(values[4])

        if values[0] in ('v2', 'v3', 'v4'):
            self._group = values[6]
        else:
            self._group = ''

        if values[0] in ('v3', 'v4'):
            self._serverHint = values[7]
        else:
            self._serverHint = ''

        if values[0] == 'v4':
            self._ssl = values[8]
            self._removeOnExit = values[9]
        else:
            self._ssl = 'n'
            self._removeOnExit = 'y'
        super().unmarshal(codecs.decode(values[5].encode(), 'hex'))

    def valuesDict(self) -> gui.ValuesDictType:
        dct = super().valuesDict()
        dct['domain'] = self._domain
        dct['ou'] = self._ou
        dct['account'] = self._account
        dct['password'] = self._password
        dct['grp'] = self._group
        dct['serverHint'] = self._serverHint
        dct['ssl'] = self._ssl == 'y'
        dct['removeOnExit'] = self._removeOnExit == 'y'
        return dct
