# pylint: disable=no-member

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
import collections.abc

import dns.resolver
import ldap

from django.utils.translation import gettext_noop as _
from uds.core.ui import gui
from uds.core.managers.crypto import CryptoManager
from uds.core import environment, exceptions, types
from uds.core.util import fields, log, ldaputil

from .windows import WindowsOsManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService


logger = logging.getLogger(__name__)


class WinDomainOsManager(WindowsOsManager):
    type_name = _('Windows Domain OS Manager')
    type_type = 'WinDomainManager'
    type_description = _('Os Manager to control windows machines with domain.')
    icon_file = 'wosmanager.png'

    # Apart form data from windows os manager, we need also domain and credentials
    domain = gui.TextField(
        length=64,
        label=_('Domain'),
        order=1,
        tooltip=_('Domain to join machines to (use FQDN form, Netbios name not supported for most operations)'),
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
        tooltip=_('Group to which add machines on creation. If empty, no group will be used.'),
        tab=types.ui.Tab.ADVANCED,
    )
    remove_on_exit = gui.CheckBoxField(
        label=_('Machine clean'),
        order=8,
        tooltip=_(
            'If checked, UDS will try to remove the machine from the domain USING the provided credentials'
        ),
        tab=types.ui.Tab.ADVANCED,
        default=True,
    )

    server_hint = gui.TextField(
        length=64,
        label=_('Server Hint'),
        order=9,
        tooltip=_(
            'In case of several AD servers, which one is preferred (only used for group and account removal operations)'
        ),
        tab=types.ui.Tab.ADVANCED,
    )
    use_ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=10,
        tooltip=_('If checked,  a ssl connection to Active Directory will be used'),
        tab=types.ui.Tab.ADVANCED,
        default=True,
        old_field_name='ssl',
    )
    timeout = fields.timeout_field(order=11, default=10, tab=types.ui.Tab.ADVANCED)

    # Inherits base "on_logout"
    on_logout = WindowsOsManager.on_logout
    idle = WindowsOsManager.idle
    deadline = WindowsOsManager.deadline

    def initialize(self, values: 'types.core.ValuesType') -> None:
        if values:
            # Some cleaning of input data (remove spaces, etc..)
            for fld in (self.domain, self.account, self.ou, self.grp, self.server_hint):
                fld.value = fld.value.strip().replace(' ', '')

            if self.domain.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide a domain!'))
            if self.account.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide an account to add machines to domain!'))
            if self.account.as_str().find('\\') != -1:
                raise exceptions.ui.ValidationError(_('DOM\\USER form is not allowed! for account'))
            if self.password.as_str() == '':
                raise exceptions.ui.ValidationError(_('Must provide a password for the account!'))

            # Fix ou based on domain if needed
            if self.domain.as_str() and self.ou.as_str():
                lpath = 'dc=' + ',dc='.join((s.lower() for s in self.domain.as_str().split('.')))
                if lpath not in self.ou.as_str().lower():  # If not in ou, add it
                    self.ou.value = self.ou.as_str() + ',' + lpath

    def _get_server_list(self) -> collections.abc.Iterable[tuple[str, int]]:
        if self.server_hint.as_str() != '':
            yield (self.server_hint.as_str(), 389)

        server: typing.Any

        def key(server: typing.Any) -> int:
            return server.priority * 10000 + server.weight

        for server in reversed(
            sorted(
                iter(typing.cast(collections.abc.Iterable[typing.Any], dns.resolver.resolve('_ldap._tcp.' + self.domain.as_str(), 'SRV'))),
                key=key,
            )
        ):
            yield (str(server.target)[:-1], server.port)

    def _connect_ldap(
        self, servers: typing.Optional[collections.abc.Iterable[tuple[str, int]]] = None
    ) -> typing.Any:
        """
        Tries to connect to LDAP
        Raises an exception if not found:
            dns.resolver.NXDOMAIN
            ldaputil.LDAPError
        """
        if servers is None:
            servers = self._get_server_list()

        account = self.account.as_str()
        if account.find('@') == -1:
            account += '@' + self.domain.as_str()

        _error_string = "No servers found"
        # And if not possible, try using NON-SSL
        for server in servers:
            ssl = self.use_ssl.as_bool()
            port = server[1] if not ssl else -1
            try:
                return ldaputil.connection(
                    account,
                    self.account.as_str(),
                    server[0],
                    port=port,
                    ssl=ssl,
                    timeout=self.timeout.as_int(),
                    debug=False,
                )
            except Exception as e:
                _error_string = f'Error: {e}'

        raise ldaputil.LDAPError(_error_string)

    def _get_group(self, ldapConnection: 'ldaputil.LDAPObject') -> typing.Optional[str]:
        base = ','.join(['DC=' + i for i in self.domain.as_str().split('.')])
        group = ldaputil.escape(self.grp.as_str())
        obj: typing.Optional[collections.abc.MutableMapping[str, typing.Any]]
        try:
            obj = next(
                ldaputil.as_dict(
                    ldapConnection,
                    base,
                    f'(&(objectClass=group)(|(cn={group})(sAMAccountName={group})))',
                    ['dn'],
                    limit=50,
                )
            )
        except StopIteration:
            obj = None

        if obj is None:
            return None

        return obj['dn']  # Returns the DN

    def _get_machine(self, ldap_connection: 'ldaputil.LDAPObject', machine_name: str) -> typing.Optional[str]:
        # if self.ou.as_str():
        #     base = self.ou.as_str()
        # else:
        base = ','.join(['DC=' + i for i in self.domain.as_str().split('.')])

        fltr = f'(&(objectClass=computer)(sAMAccountName={ldaputil.escape(machine_name)}$))'
        obj: typing.Optional[collections.abc.MutableMapping[str, typing.Any]]
        try:
            obj = next(ldaputil.as_dict(ldap_connection, base, fltr, ['dn'], limit=50))
        except StopIteration:
            obj = None

        if obj is None:
            return None

        return obj['dn']  # Returns the DN

    def ready_notified(self, userservice: 'UserService') -> None:
        # No group to add
        if self.grp.as_str() == '':
            return

        if '.' not in self.domain.as_str():
            logger.info('Adding to a group for a non FQDN domain is not supported')
            return

        # The machine is on a AD for sure, and maybe they are not already sync
        error: typing.Optional[str] = None
        for s in self._get_server_list():
            try:
                ldap_connection = self._connect_ldap(servers=(s,))

                machine = self._get_machine(ldap_connection, userservice.friendly_name)
                group = self._get_group(ldap_connection)
                # #
                # Direct LDAP operation "modify", maybe this need to be added to ldaputil? :)
                # #
                ldap_connection.modify_s(
                    group, ((ldap.MOD_ADD, 'member', [machine.encode()]),)  # type: ignore  # (valid)
                )  # @UndefinedVariable
                error = None
                break
            except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
                logger.warning('Could not find _ldap._tcp.%s', self.domain.as_str())
                log.log(
                    userservice,
                    log.LogLevel.WARNING,
                    f'Could not remove machine from domain (_ldap._tcp.{self.domain.as_str()} not found)',
                    log.LogSource.OSMANAGER,
                )
            except ldaputil.ALREADY_EXISTS:  # pyright: ignore
                # Already added this machine to this group, pass
                error = None
                break
            except ldaputil.LDAPError:
                logger.exception('Ldap Exception caught')
                error = f'Could not add machine (invalid credentials? for {self.account.as_str()})'
            except Exception as e:
                error = f'Could not add machine {userservice.friendly_name} to group {self.grp.as_str()}: {e}'
                # logger.exception('Ldap Exception caught')

        if error:
            log.log(userservice, log.LogLevel.WARNING, error, log.LogSource.OSMANAGER)
            logger.error(error)

    def release(self, userservice: 'UserService') -> None:
        super().release(userservice)

        # If no removal requested, just return
        if self.remove_on_exit.as_bool() is False:
            return

        if '.' not in self.domain.as_str():
            # logger.info('Releasing from a not FQDN domain is not supported')
            log.log(
                userservice,
                log.LogLevel.INFO,
                "Removing a domain machine form a non FQDN domain is not supported.",
                log.LogSource.OSMANAGER,
            )
            return

        try:
            ldap_connection = self._connect_ldap()
        except dns.resolver.NXDOMAIN:  # No domain found, log it and pass
            logger.warning('Could not find _ldap._tcp.%s', self.domain.as_str())
            log.log(
                userservice,
                log.LogLevel.WARNING,
                f'Could not remove machine from domain (_ldap._tcp.{self.domain.as_str()} not found)',
                log.LogSource.OSMANAGER,
            )
            return
        except ldaputil.LDAPError as e:
            # logger.exception('Ldap Exception caught')
            log.log(
                userservice,
                log.LogLevel.WARNING,
                f'Could not remove machine from domain ({e})',
                log.LogSource.OSMANAGER,
            )
            return
        except Exception as e:
            # logger.exception('Exception caught')
            log.log(
                userservice,
                log.LogLevel.WARNING,
                f'Could not remove machine from domain ({e})',
                log.LogSource.OSMANAGER,
            )
            return

        try:
            res = self._get_machine(ldap_connection, userservice.friendly_name)
            if res is None:
                raise Exception(f'Machine {userservice.friendly_name} not found on AD (permissions?)')
            ldaputil.recursive_delete(ldap_connection, res)
        except IndexError:
            logger.error('Error deleting %s from BASE %s', userservice.friendly_name, self.ou.as_str())
        except Exception:
            logger.exception('Deleting from AD: ')

    def check(self) -> str:
        try:
            ldap_connection = self._connect_ldap()
        except ldaputil.LDAPError as e:
            return _('Check error: {}').format(e)
        except dns.resolver.NXDOMAIN:
            return _('Could not find server parameters (_ldap._tcp.{0} can\'t be resolved)').format(
                self.domain.as_str()
            )
        except Exception as e:
            logger.exception('Exception ')
            return str(e)

        try:
            ldap_connection.search_st(self.ou.as_str(), ldaputil.SCOPE_BASE)  # pyright: ignore
        except ldaputil.LDAPError as e:
            return _('Check error: {}').format(e)

        # Group
        if self.grp.as_str() != '':
            if self._get_group(ldap_connection) is None:
                return _('Check Error: group "{}" not found (using "cn" to locate it)').format(
                    self.grp.as_str()
                )

        return _('Server check was successful')

    # pylint: disable=protected-access
    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        logger.debug('Test invoked')
        wd = WinDomainOsManager(env, data)
        logger.debug(wd)
        try:
            try:
                ldap_connection = wd._connect_ldap()
            except ldaputil.LDAPError as e:
                return types.core.TestResult(
                    False,
                    _('Could not access AD using LDAP ({0})').format(e),
                )

            ou = wd.ou.as_str()
            if ou == '':
                ou = 'cn=Computers,dc=' + ',dc='.join(wd.domain.as_str().split('.'))

            logger.info('Checking %s with ou %s', wd.domain.as_str(), ou)
            r = ldap_connection.search_st(ou, ldaputil.SCOPE_BASE)
            logger.info('Result of search: %s', r)

        except ldaputil.LDAPError:
            if wd and not wd.ou.as_str():
                return types.core.TestResult(
                    False,
                    _('The default path for computers was not found!!!'),
                )
            return types.core.TestResult(
                False,
                _('The ou path {0} was not found!!!').format(wd.ou.as_str()),
            )
        except dns.resolver.NXDOMAIN:
            return types.core.TestResult(
                False,
                _('Could not check parameters (_ldap._tcp.{0} can\'t be resolved)').format(wd.domain.as_str()),
            )
        except Exception as e:
            return types.core.TestResult(
                False,
                _('Unknown error: {0}').format(e),
            )

        return types.core.TestResult(True)

    def actor_data(self, userservice: 'UserService') -> collections.abc.MutableMapping[str, typing.Any]:
        return {
            'action': 'rename_ad',
            'name': userservice.get_name(),
            # Repeat data, to keep compat with old versions of Actor
            # Will be removed in a couple of versions
            'ad': self.domain.as_str(),
            'ou': self.ou.as_str(),
            'username': self.account.as_str(),
            'password': self.account.as_str(),
            'custom': {
                'domain': self.domain.as_str(),
                'ou': self.ou.as_str(),
                'username': self.account.as_str(),
                'password': self.account.as_str(),
            },
        }

    def unmarshal(self, data: bytes) -> None:
        if not data.startswith(b'v'):
            return super().unmarshal(data)

        values = data.decode('utf8').split('\t')
        if values[0] in ('v1', 'v2', 'v3', 'v4'):
            self.domain.value = values[1]
            self.ou.value = values[2]
            self.account.value = values[3]
            self.password.value = CryptoManager().decrypt(values[4])

        if values[0] in ('v2', 'v3', 'v4'):
            self.grp.value = values[6]
        else:
            self.grp.value = ''

        if values[0] in ('v3', 'v4'):
            self.server_hint.value = values[7]
        else:
            self.server_hint.value = ''

        if values[0] == 'v4':
            self.use_ssl.value = values[8] == 'y'
            self.remove_on_exit.value = values[9] == 'y'
        else:
            self.use_ssl.value = False
            self.remove_on_exit.value = True
        super().unmarshal(codecs.decode(values[5].encode(), 'hex'))

        self.mark_for_upgrade()  # Force upgrade to new format
