# pyright: reportUnknownMemberType=false
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
Converted to ldap3 by GitHub Copilot
"""
import logging
import typing
import collections.abc
import ssl

from ldap3 import (
    Server,
    Connection,
    Tls,
    ALL,
    SUBTREE,
    BASE,
    LEVEL,
    ALL_ATTRIBUTES,
    SIMPLE,
    MODIFY_ADD as LDAP_MODIFY_ADD,
    MODIFY_DELETE as LDAP_MODIFY_DELETE,
    MODIFY_REPLACE as LDAP_MODIFY_REPLACE,
    MODIFY_INCREMENT as LDAP_MODIFY_INCREMENT,
)

from django.utils.translation import gettext as _
from django.conf import settings

from uds.core.util import utils

logger = logging.getLogger(__name__)

# Re-export with our nomenclature
SCOPE_BASE = BASE
SCOPE_SUBTREE = SUBTREE
SCOPE_ONELEVEL = LEVEL

# Also for modify operations
MODIFY_ADD = LDAP_MODIFY_ADD
MODIFY_DELETE = LDAP_MODIFY_DELETE
MODIFY_REPLACE = LDAP_MODIFY_REPLACE
MODIFY_INCREMENT = LDAP_MODIFY_INCREMENT

LDAPResultType = collections.abc.MutableMapping[str, typing.Any]
LDAPSearchResultType = typing.Optional[list[dict[str, typing.Any]]]

LDAPConnection: typing.TypeAlias = Connection


class LDAPError(Exception):
    @staticmethod
    def reraise(e: typing.Any) -> typing.NoReturn:
        _str = _('Connection error: ')
        _str += str(e)
        raise LDAPError(_str) from e


def escape(value: str) -> str:
    """
    Escape filter chars for ldap search filter
    """
    # ldap3 does not provide a direct escape, but this is a safe replacement
    return (
        value.replace('\\', '\\5c')
        .replace('*', '\\2a')
        .replace('(', '\\28')
        .replace(')', '\\29')
        .replace('\0', '\\00')
    )


def connection(
    username: str,
    passwd: str,
    host: str,
    *,
    port: int = -1,
    read_only: bool = True,  # Most times we want read-only connections, so default to True
    use_ssl: bool = False,
    timeout: int = 3,
    debug: bool = False,
    verify_ssl: bool = False,
    certificate_data: typing.Optional[str] = None,  # Content of the certificate, not the file itself
) -> 'LDAPConnection':
    """
    Tries to connect to ldap using ldap3. If username is None, it tries to connect using user provided credentials.
    """
    logger.debug('Login in to %s as user %s', host, username)

    if port == -1:
        port = 636 if use_ssl else 389
    tls = None

    if use_ssl:
        # Use ldap3's own constants for validate and version, not ssl module
        tls_validate = ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE

        if hasattr(settings, 'SECURE_MIN_TLS_VERSION') and settings.SECURE_MIN_TLS_VERSION:
            # format is "1.0, 1.1, 1.2 or 1.3", convert to ssl.TLSVersion.TLSv1_0, ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_2 or ssl.TLSVersion.TLSv1_3
            tls_version = getattr(ssl.TLSVersion, 'TLSv' + settings.SECURE_MIN_TLS_VERSION.replace('.', '_'))
        else:
            tls_version = ssl.TLSVersion.TLSv1_2

        if hasattr(settings, 'SECURE_CIPHERS') and settings.SECURE_CIPHERS:
            cipher = settings.SECURE_CIPHERS
        else:
            cipher = None

        tls = Tls(
            ca_certs_data=certificate_data,
            validate=tls_validate,
            version=tls_version,
            ciphers=cipher,
        )
    server = Server(
        host,
        port=port,
        use_ssl=use_ssl,
        get_info=ALL,
        tls=tls,
    )
    try:
        conn = Connection(
            server,
            user=username,
            password=passwd,
            read_only=read_only,
            authentication=SIMPLE,
            receive_timeout=timeout,
        )
        conn.open()
        if not conn.bind():
            logger.error('Could not bind to LDAP server %s as user %s', host, username)
            raise LDAPError(_('Could not bind to LDAP server: {host}').format(host=host))

        logger.debug('Connection was successful')
        return conn
    except Exception as e:
        logger.exception('Exception connection:')
        raise LDAPError(str(e)) from e


def as_dict(
    con: Connection,
    base: str,
    ldap_filter: str,
    *,
    attributes: typing.Optional[collections.abc.Iterable[str]] = None,
    limit: int = 100,
    scope: typing.Any = SCOPE_SUBTREE,
) -> typing.Generator[LDAPResultType, None, None]:
    """
    Makes a search on LDAP, returns a generator with the results, where each result is a dictionary where values are always a list of strings
    """
    logger.debug('Filter: %s, attr list: %s', ldap_filter, attributes)
    attr_list = list(attributes) if attributes else ALL_ATTRIBUTES
    try:
        con.search(
            search_base=base,
            search_filter=ldap_filter,
            search_scope=scope,
            attributes=attr_list,
            size_limit=limit,
        )
        for entry in typing.cast(typing.Any, con.entries):
            dct = utils.CaseInsensitiveDict[list[str]]()
            for attr in attr_list:
                dct[attr] = entry[attr].values if attr in entry else ['']
            dct['dn'] = entry.entry_dn
            yield dct
    except Exception as e:
        logger.exception('Exception in search:')
        raise LDAPError(str(e)) from e


def first(
    con: Connection,
    base: str,
    object_class: str,
    field: str,
    value: str,
    *,
    attributes: typing.Optional[collections.abc.Iterable[str]] = None,
    max_entries: int = 50,
) -> typing.Optional[LDAPResultType]:
    """
    Searchs for the username and returns its LDAP entry
    """
    value = escape(value)
    attr_list = [field] + list(attributes) if attributes else [field]
    ldap_filter = f'(&(objectClass={object_class})({field}={value}))'
    try:
        gen = as_dict(con, base, ldap_filter, attributes=attr_list, limit=max_entries)
        obj = next(gen)
    except StopIteration:
        return None
    obj['_id'] = value
    return obj


def add(
    con: Connection,
    dn: str,
    *,
    attributes: dict[str, list[bytes | str]],
) -> bool:
    """
    Adds a new LDAP entry.
    Args:
        con: LDAP connection
        dn: Distinguished Name of the entry to add
        attributes: Dictionary of attributes, e.g. { 'objectClass': ['user'], ... }
    Returns:
        True if the operation was successful, raises LDAPError otherwise
    """
    try:
        result = typing.cast(typing.Any, con.add(dn, attributes))
        if not result:
            raise LDAPError(f'Add operation failed: {con.result}')
        return True
    except Exception as e:
        logger.exception('Exception in add:')
        raise LDAPError(str(e)) from e



def delete(con: Connection, dn: str, *, depth: int = 1) -> None:
    """
    Deletes an LDAP entry and its children up to a certain depth.
    Args:
        con: LDAP connection
        dn: Distinguished Name of the entry to delete
        depth: How many levels to delete (1=only direct children, 2=children and grandchildren, <1=all levels)
    Returns:
        None. Raises LDAPError on failure.
    """
    try:
        con.search(dn, '(objectClass=*)', search_scope=SCOPE_ONELEVEL, attributes=['dn'])
        for entry in typing.cast(list[typing.Any], con.entries):
            child_dn: str = entry.entry_dn
            delete(con, child_dn, depth=depth - 1)
            result = typing.cast(typing.Any, con.delete(child_dn))
            if not result:
                raise LDAPError(f'Delete operation failed: {con.result}')
        result = typing.cast(typing.Any, con.delete(dn))
        if not result:
            raise LDAPError(f'Delete operation failed: {con.result}')
    except Exception as e:
        logger.exception('Exception in delete:')
        raise LDAPError(str(e)) from e

def recursive_delete(con: Connection, base_dn: str) -> None:
    """
    Deletes all direct children and the entry itself (one level deep, for compatibility).
    """
    delete(con, base_dn, depth=1)


def modify(
    con: Connection,
    dn: str,
    changes: dict[str, list[tuple[str, list[bytes | str]]]],
    *,
    controls: typing.Any = None,
) -> bool:
    """
    Performs a modify operation on the LDAP entry.
    Args:
        con: LDAP connection
        dn: Distinguished Name of the entry to modify
        changes: Dictionary of changes, e.g. { 'member': [(MODIFY_ADD, [b'userdn'])] }
        controls: Optional controls
    Returns:
        True if the operation was successful, raises LDAPError otherwise
    """
    try:
        result = typing.cast(typing.Any, con.modify(dn, changes, controls=controls))
        if not result:
            raise LDAPError(f'Modify operation failed: {con.result}')
        return True
    except Exception as e:
        logger.exception('Exception in modify:')
        raise LDAPError(str(e)) from e


def get_root_dse(con: Connection) -> typing.Optional[LDAPResultType]:
    con.search('', '(objectClass=*)', search_scope=SCOPE_BASE)
    if con.entries:
        entry = typing.cast(typing.Any, con.entries[0])
        dct: dict[str, typing.Any] = {attr: entry[attr].values for attr in entry.entry_attributes}
        dct['dn'] = entry.entry_dn
        return dct
    return None
