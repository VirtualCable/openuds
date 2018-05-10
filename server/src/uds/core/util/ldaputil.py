# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 Virtual Cable S.L.
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pylint: disable=no-name-in-module,import-error, maybe-no-member
from __future__ import unicode_literals

from django.utils.translation import ugettext as _

import ldap.filter
import six
import logging
from uds.core.util import tools

logger = logging.getLogger(__name__)


class LDAPError(Exception):

    @staticmethod
    def reraise(e):
        _str = _('Connection error: ')
        if hasattr(e, 'message') and isinstance(e.message, dict):
            _str += ', '.join((e.message.get('info', ''), e.message.get('desc')))
        else:
            _str += "{}".format(e)
        raise LDAPError(_str)


def escape(value):
    """
    Escape filter chars for ldap search filter
    """
    return ldap.filter.escape_filter_chars(tools.b2(value))


def connection(username, password, host, port=-1, ssl=False, timeout=3, debug=False):
    """
    Tries to connect to ldap. If username is None, it tries to connect using user provided credentials.
    @param username: Username for connection validation
    @param password: Password for connection validation
    @return: Connection established
    @raise exception: If connection could not be established
    """
    logger.debug('Login in to {} as user {}'.format(host, username))
    l = None
    if isinstance(password, six.text_type):
        password = password.encode('utf-8')
    try:
        if debug:
            ldap.set_option(ldap.OPT_DEBUG_LEVEL, 9)
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
        schema = ssl and 'ldaps' or 'ldap'
        if port == -1:
            port = ssl and 636 or 389
        uri = "{}://{}:{}".format(schema, host, port)
        logger.debug('Ldap uri: {}'.format(uri))

        l = ldap.initialize(uri=uri)
        l.set_option(ldap.OPT_REFERRALS, 0)
        l.network_timeout = l.timeout = int(timeout)
        l.protocol_version = ldap.VERSION3

        l.simple_bind_s(who=username, cred=password)
    except ldap.SERVER_DOWN:
        raise LDAPError(_('Can\'t contact LDAP server'))
    except ldap.LDAPError as e:
        LDAPError.reraise(e)
    except Exception as e:
        logger.exception('Exception connection:')
        raise LDAPError('{}'.format(e))

    logger.debug('Conneciton was success')
    return l


def getAsDict(con, base, ldapFilter, attrList, sizeLimit, scope=ldap.SCOPE_SUBTREE):
    """
    Makes a search on LDAP, adjusting string to required type (ascii on python2, str on python3).
    returns an generator with the results, where each result is a dictionary where it values are always a list of strings
    """
    logger.debug('Filter: {}, attr list: {}'.format(ldapFilter, attrList))

    if attrList is not None:
        attrList = [tools.b2(i) for i in attrList]

    res = None
    try:
        # On python2, attrs and search string is str (not unicode), in 3, str (not bytes)
        res = con.search_ext_s(
            base,
            scope=scope,
            filterstr=tools.b2(ldapFilter),
            attrlist=attrList,
            sizelimit=sizeLimit
        )
    except ldap.LDAPError as e:
        LDAPError.reraise(e)
    except Exception as e:
        logger.exception('Exception connection:')
        raise LDAPError('{}'.format(e))

    logger.debug('Result of search {} on {}: {}'.format(ldapFilter, base, res))

    if res is not None:
        for r in res:
            if r[0] is None:
                continue  # Skip None entities

            # Convert back attritutes to test_type ONLY on python2
            dct = tools.CaseInsensitiveDict((k, ['']) for k in attrList) if attrList is not None else tools.CaseInsensitiveDict()

            # Convert back result fields to str
            for k, v in six.iteritems(r[1]):
                dct[tools.u2(k)] = list(i.decode('utf8', errors='replace') for i in v)

            dct.update({'dn': r[0]})

            yield dct


def getFirst(con, base, objectClass, field, value, attributes=None, sizeLimit=50):
    """
    Searchs for the username and returns its LDAP entry
    @param username: username to search, using user provided parameters at configuration to map search entries.
    @param objectClass: Objectclass of the user mane username to search.
    @return: None if username is not found, an dictionary of LDAP entry attributes if found (all in unicode on py2, str on py3).
    """
    value = ldap.filter.escape_filter_chars(tools.b2(value))
    # Convert atttribute list to bynary ONLY on python2
    attrList = [field] + [i for i in attributes]

    ldapFilter = '(&(objectClass={})({}={}))'.format(objectClass, field, value)

    try:
        obj = next(getAsDict(con, base, ldapFilter, attrList, sizeLimit))
    except StopIteration:
        return None  # None found

    obj['_id'] = value

    return obj


# Recursive delete
def recursive_delete(con, base_dn):
    search = con.search_s(base_dn, ldap.SCOPE_ONELEVEL)

    for dn, _ in search:
        # recursive_delete(conn, dn)
        # RIGHT NOW IS NOT RECURSIVE, JUST 1 LEVEL BELOW!!!
        con.delete_s(dn)

    con.delete_s(base_dn)

