# pylint: disable=no-member

#
# Copyright (c) 2016-2021 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc
import tempfile
import os.path

import ldap.filter

# Import for local use, and reexport
from ldap import (
    SCOPE_BASE as S_BASE,  # pyright: ignore
    SCOPE_SUBTREE as S_SUBTREE,  # pyright: ignore
    SCOPE_ONELEVEL as S_ONELEVEL,  # pyright: ignore
    ALREADY_EXISTS as S_ALREADY_EX,  # pyright: ignore
    # SCOPE_SUBORDINATE,  # pyright: ignore
)

# Reexporting, so we can use them as ldaputil.SCOPE_BASE, etc...
# This allows us to replace this in a future with another ldap library if needed
SCOPE_BASE: int = S_BASE  # pyright: ignore
SCOPE_SUBTREE: int = S_SUBTREE  # pyright: ignore
SCOPE_ONELEVEL: int = S_ONELEVEL  # pyright: ignore
ALREADY_EXISTS: int = S_ALREADY_EX  # pyright: ignore

from django.utils.translation import gettext as _
from django.conf import settings

# So it is avaliable for importers
from ldap.ldapobject import LDAPObject as S_LDAPObject  # pyright: ignore

# Reexporting, so we can use them as ldaputil.LDAPObject, etc...
# This allows us to replace this in a future with another ldap library if needed
LDAPObject: typing.TypeAlias = S_LDAPObject

from uds.core.util import utils


logger = logging.getLogger(__name__)

LDAPResultType = collections.abc.MutableMapping[str, typing.Any]
LDAPSearchResultType = typing.Optional[list[tuple[typing.Optional[str], dict[str, typing.Any]]]]

# About ldap filters: (just for reference)
# https://ldap.com/ldap-filters/


class LDAPError(Exception):
    @staticmethod
    def reraise(e: typing.Any) -> typing.NoReturn:
        _str = _('Connection error: ')
        if hasattr(e, 'message') and isinstance(getattr(e, 'message'), dict):
            _str += f'{getattr(e, "message").get("info", "")}, {e.message.get("desc", "")}'
        else:
            _str += str(e)
        raise LDAPError(_str) from e


def escape(value: str) -> str:
    """
    Escape filter chars for ldap search filter
    """
    return ldap.filter.escape_filter_chars(value)  # pyright: ignore reportGeneralTypeIssues


def connection(
    username: str,
    passwd: typing.Union[str, bytes],
    host: str,
    *,
    port: int = -1,
    ssl: bool = False,
    timeout: int = 3,
    debug: bool = False,
    verify_ssl: bool = False,
    certificate: typing.Optional[str] = None,  # Content of the certificate, not the file itself
) -> 'LDAPObject':
    """
    Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.

    Args:
        username (str): Username to use for connection
        passwd (typing.Union[str, bytes]): Password to use for connection
        host (str): Host to connect to
        port (int, optional): Port to connect to. Defaults to -1.
        ssl (bool, optional): If connection is ssl. Defaults to False.
        timeout (int, optional): Timeout for connection. Defaults to 3 seconds.
        debug (bool, optional): If debug is enabled. Defaults to False.
        verify_ssl (bool, optional): If ssl certificate must be verified. Defaults to False.
        certificate (typing.Optional[str], optional): Certificate to use for connection. Defaults to None. (only if ssl and verify_ssl are True)

    returns:
        LDAPObject: Connection object

    Raises:
        LDAPError: If connection could not be established


    @raise exception: If connection could not be established
    """
    logger.debug('Login in to %s as user %s', host, username)
    password = passwd.encode('utf-8') if isinstance(passwd, str) else passwd

    l: 'LDAPObject'
    try:
        if debug:
            ldap.set_option(ldap.OPT_DEBUG_LEVEL, 8191)  # pyright: ignore

        schema = 'ldaps' if ssl else 'ldap'
        if port == -1:
            port = 636 if ssl else 389
        uri = f'{schema}://{host}:{port}'
        logger.debug('Ldap uri: %s', uri)

        l = ldap.initialize(uri=uri)  # pyright: ignore
        l.set_option(ldap.OPT_REFERRALS, 0)  # pyright: ignore
        l.set_option(ldap.OPT_TIMEOUT, int(timeout))  # pyright: ignore
        l.network_timeout = int(timeout)
        l.protocol_version = ldap.VERSION3  # pyright: ignore

        certificate = (certificate or '').strip()

        if ssl:
            cipher_suite = getattr(settings, 'LDAP_CIPHER_SUITE', 'PFS')
            if certificate and verify_ssl:  # If not verify_ssl, we don't need the certificate
                # Create a semi-temporary ca file, with the content of the certificate
                # The name is from the host, so we can ovwerwrite it if needed
                cert_filename = os.path.join(tempfile.gettempdir(), f'ldap-cert-{host}.pem')
                with open(cert_filename, 'w') as f:
                    f.write(certificate)
                l.set_option(ldap.OPT_X_TLS_CACERTFILE, cert_filename)  # pyright: ignore
                # If enforced on settings, do no change it here
                if not getattr(settings, 'LDAP_CIPHER_SUITE', None):
                    cipher_suite = 'PFS'

            if not verify_ssl:
                l.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)  # pyright: ignore
            # Disable TLS1 and TLS1.1
            # 0x304 = TLS1.3, 0x303 = TLS1.2, 0x302 = TLS1.1, 0x301 = TLS1.0, but use ldap module constants
            # Ensure that libldap is compiled with TLS1.3 support
            minVersion = getattr(settings, 'SECURE_MIN_TLS_VERSION', '1.2')
            if hasattr(ldap, 'OPT_X_TLS_PROTOCOL_TLS1_3'):
                tls_version: typing.Any = {  # for pyright to ignore
                    '1.2': ldap.OPT_X_TLS_PROTOCOL_TLS1_2,  # pyright: ignore
                    '1.3': ldap.OPT_X_TLS_PROTOCOL_TLS1_3,  # pyright: ignore
                }.get(
                    minVersion, ldap.OPT_X_TLS_PROTOCOL_TLS1_2  # pyright: ignore
                )

                l.set_option(ldap.OPT_X_TLS_PROTOCOL_MIN, tls_version)  # pyright: ignore
            # Cipher suites are from GNU TLS, not OpenSSL
            # https://gnutls.org/manual/html_node/Priority-Strings.html for more info
            # i.e.:
            #  * NORMAL
            #  * NORMAL:-VERS-TLS-ALL:+VERS-TLS1.2:+VERS-TLS1.3
            #  * PFS
            #  * SECURE256
            #
            #  Note: Your distro could have compiled libldap with OpenSSL, so this will not work
            #  You can simply use OpenSSL cipher suites, but you will need to test them
            try:
                l.set_option(ldap.OPT_X_TLS_CIPHER_SUITE, cipher_suite)  # pyright: ignore
                l.set_option(ldap.OPT_X_TLS_NEWCTX, 0)  # pyright: ignore
            except Exception:
                logger.info('Cipher suite %s not supported by libldap', cipher_suite)

        l.simple_bind_s(who=username, cred=password)  # pyright: ignore reportGeneralTypeIssues

        logger.debug('Connection was successful')
        return l
    except ldap.SERVER_DOWN as e:  # pyright: ignore
        raise LDAPError(_('Can\'t contact LDAP server') + f': {e}') from e
    except ldap.LDAPError as e:  # pyright: ignore
        LDAPError.reraise(e)
    except Exception as e:
        logger.exception('Exception connection:')
        raise LDAPError(str(e)) from e

    raise LDAPError(_('Unknown error'))


def as_dict(
    con: 'LDAPObject',
    base: str,
    ldap_filter: str,
    attributes: typing.Optional[collections.abc.Iterable[str]] = None,
    limit: int = 100,
    scope: typing.Any = SCOPE_SUBTREE,
) -> typing.Generator[LDAPResultType, None, None]:
    """
    Makes a search on LDAP, adjusting string to required type (ascii on python2, str on python3).
    returns an generator with the results, where each result is a dictionary where it values are always a list of strings
    """
    logger.debug('Filter: %s, attr list: %s', ldap_filter, attributes)

    if attributes:
        attributes = list(attributes)  # Ensures iterable is a list

    res: LDAPSearchResultType = None
    try:
        # On python2, attrs and search string is str (not unicode), in 3, str (not bytes)
        res = con.search_ext_s(  # pyright: ignore reportGeneralTypeIssues
            base,
            scope=scope,
            filterstr=ldap_filter,
            attrlist=attributes,
            sizelimit=limit,
        )
    except ldap.LDAPError as e:  # pyright: ignore
        LDAPError.reraise(e)
    except Exception as e:
        logger.exception('Exception connection:')
        raise LDAPError(str(e)) from e

    logger.debug(
        'Result of search %s on %s: %s', ldap_filter, base, res
    )  # pyright: ignore reportGeneralTypeIssues

    if res is not None:
        for r in res:
            if r[0] is None:
                continue  # Skip None entities

            # Convert back attritutes to test_type ONLY on python2
            dct: dict[str, typing.Any] = (
                utils.CaseInsensitiveDict[list[str]]((k, ['']) for k in attributes)
                if attributes is not None
                else utils.CaseInsensitiveDict[list[str]]()
            )

            # Convert back result fields to str
            for k, v in r[1].items():
                dct[k] = list(i.decode('utf8', errors='replace') for i in v)

            dct.update({'dn': r[0]})

            yield dct


def first(
    con: 'LDAPObject',
    base: str,
    objectClass: str,
    field: str,
    value: str,
    attributes: typing.Optional[collections.abc.Iterable[str]] = None,
    sizeLimit: int = 50,
) -> typing.Optional[LDAPResultType]:
    """
    Searchs for the username and returns its LDAP entry
    @param username: username to search, using user provided parameters at configuration to map search entries.
    @param objectClass: Objectclass of the user mane username to search.
    @return: None if username is not found, an dictionary of LDAP entry attributes if found (all in unicode on py2, str on py3).
    """
    value = ldap.filter.escape_filter_chars(value)  # pyright: ignore reportGeneralTypeIssues

    attrList = [field] + list(attributes) if attributes else []

    ldapFilter = f'(&(objectClass={objectClass})({field}={value}))'

    try:
        obj = next(as_dict(con, base, ldapFilter, attrList, sizeLimit))
    except StopIteration:
        return None  # None found

    obj['_id'] = value

    return obj


# Recursive delete
def recursive_delete(con: 'LDAPObject', base_dn: str) -> None:
    search: LDAPSearchResultType = con.search_s(base_dn, SCOPE_ONELEVEL)  # pyright: ignore reportGeneralTypeIssues
    if search:
        for found in search:
            # recursive_delete(conn, dn)
            # RIGHT NOW IS NOT RECURSIVE, JUST 1 LEVEL BELOW!!!
            con.delete_s(found[0])  # pyright: ignore reportGeneralTypeIssues

    con.delete_s(base_dn)  # pyright: ignore reportGeneralTypeIssues


def get_root_dse(con: 'LDAPObject') -> typing.Optional[LDAPResultType]:
    """
    Gets the root DSE of the LDAP server
    @param cont: Connection to LDAP server
    @return: None if root DSE is not found, an dictionary of LDAP entry attributes if found (all in unicode on py2, str on py3).
    """
    return next(
        as_dict(
            con=con,
            base='',
            ldap_filter='(objectClass=*)',
            scope=SCOPE_BASE,
        )
    )
