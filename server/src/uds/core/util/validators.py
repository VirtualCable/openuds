# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import re
import logging
import typing
import json

from django.utils.translation import gettext as _
from django.core import validators as dj_validators

from cryptography.x509 import load_pem_x509_certificate

from uds.core import exceptions
from uds.core.util import security

logger = logging.getLogger(__name__)

url_validator = dj_validators.URLValidator(['http', 'https'])


def validate_numeric(
    value: typing.Union[str, int],
    min_value: typing.Optional[int] = None,
    max_value: typing.Optional[int] = None,
    field_name: typing.Optional[str] = None,
) -> int:
    """
    Validates that a numeric value is valid
    :param numericStr: Numeric value to check (as string)
    :param min_value: If not None, min value that must be the numeric or exception is thrown
    :param max_value: If not None, max value that must be the numeric or exception is thrown
    :param returnAsInteger: if True, returs value as integer (default), else returns as string
    :param fieldName: If present, the name of the field for "Raising" exceptions, defaults to "Numeric value"
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    value = str(value).replace(' ', '')
    field_name = field_name or _('Numeric')

    try:
        numeric = int(value)
        if min_value is not None and numeric < min_value:
            raise exceptions.ui.ValidationError(
                _('{0} must be greater than or equal to {1}').format(field_name, min_value)
            )

        if max_value is not None and numeric > max_value:
            raise exceptions.ui.ValidationError(
                _('{0} must be lower than or equal to {1}').format(field_name, max_value)
            )

        value = str(numeric)

    except ValueError:
        raise exceptions.ui.ValidationError(_('{0} contains invalid characters').format(field_name)) from None

    return int(value)


def validate_hostname(hostname: str, max_length: int = 64, domain_allowed: bool=False, field_name: typing.Optional[str] = None) -> str:
    field_name = f' (On field {field_name})' if field_name else ''
    if len(hostname) > max_length:
        raise exceptions.ui.ValidationError(
            _('{} is not a valid hostname: maximum host name length exceeded.').format(hostname + field_name)
        )

    if not domain_allowed:
        if '.' in hostname:
            raise exceptions.ui.ValidationError(
                _('{} is not a valid hostname: (domains not allowed)').format(hostname + field_name)
            )

    allowed = re.compile(r'(?!-)[A-Z\d-]{1,63}(?<!-)$', re.IGNORECASE)

    if not all(allowed.match(x) for x in hostname.split(".")):
        raise exceptions.ui.ValidationError(_('{} is not a valid hostname: (invalid characters)').format(hostname + field_name))

    return hostname


def validate_fqdn(fqdn: str, maxLength: int = 255, field_name: typing.Optional[str] = None) -> str:
    return validate_hostname(fqdn, maxLength, domain_allowed=True, field_name=field_name)


def validateUrl(url: str, maxLength: int = 1024, field_name: typing.Optional[str] = None) -> str:
    field_name = f' (On field {field_name})' if field_name else ''
    if len(url) > maxLength:
        raise exceptions.ui.ValidationError(_('{} is not a valid URL: exceeds maximum length.').format(url + field_name))

    try:
        url_validator(url)
    except Exception as e:
        raise exceptions.ui.ValidationError(str(e))

    return url


def validate_ipv4(ipv4: str, field_name: typing.Optional[str] = None) -> str:
    """
    Validates that a ipv4 address is valid
    :param ipv4: ipv4 address to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    field_name = f' (On field {field_name})' if field_name else ''
    try:
        dj_validators.validate_ipv4_address(ipv4)
    except Exception:
        raise exceptions.ui.ValidationError(_('{} is not a valid IPv4 address').format(ipv4 + field_name)) from None
    return ipv4


def validate_ipv6(ipv6: str, field_name: typing.Optional[str] = None) -> str:
    """
    Validates that a ipv6 address is valid
    :param ipv6: ipv6 address to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    field_name = f' (On field {field_name})' if field_name else ''
    try:
        dj_validators.validate_ipv6_address(ipv6)
    except Exception:
        raise exceptions.ui.ValidationError(_('{} is not a valid IPv6 address').format(ipv6 + field_name)) from None
    return ipv6


def validate_ip(ipv4_or_ipv6: str, field_name: typing.Optional[str] = None) -> str:
    """
    Validates that a ipv4 or ipv6 address is valid
    :param ipv4OrIpv6: ipv4 or ipv6 address to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    field_name = f' (On field {field_name})' if field_name else ''
    try:
        dj_validators.validate_ipv46_address(ipv4_or_ipv6)
    except Exception:
        raise exceptions.ui.ValidationError(
            _('{} is not a valid IPv4 or IPv6 address').format(ipv4_or_ipv6 + field_name)
        ) from None
    return ipv4_or_ipv6


def validate_path(
    path: str,
    max_length: int = 1024,
    must_be_windows: bool = False,
    must_be_unix: bool = False,
    field_name: typing.Optional[str] = None,
) -> str:
    """
    Validates a path, if not "mustBe" is specified, it will be validated as either windows or unix.
    Path must be absolute, and must not exceed maxLength
    Args:
        path (str): path to validate
        max_length (int, optional): max length of path. Defaults to 1024.
        must_be_windows (bool, optional): if True, path must be a windows path. Defaults to False.
        must_be_unix (bool, optional): if True, path must be a unix path. Defaults to False.

    Raises:
        exceptions.ValidationException: if path is not valid

    Returns:
        str: path
    """
    field_name = f' (On field {field_name})' if field_name else ''
    if len(path) > max_length:
        raise exceptions.ui.ValidationError(_('{} exceeds maximum path length.').format(path + field_name))

    valid_for_windows = re.compile(r'^[a-zA-Z]:\\.*$')
    valid_for_unix = re.compile(r'^/.*$')

    if must_be_windows:
        if not valid_for_windows.match(path):
            raise exceptions.ui.ValidationError(_('{} is not a valid windows path').format(path + field_name))
    elif must_be_unix:
        if not valid_for_unix.match(path):
            raise exceptions.ui.ValidationError(_('{} is not a valid unix path').format(path + field_name))
    else:
        if not valid_for_windows.match(path) and not valid_for_unix.match(path):
            raise exceptions.ui.ValidationError(_('{} is not a valid path').format(path + field_name))

    return path


def validate_port(port: typing.Union[str, int], *, field_name: typing.Optional[str] = None, valid_default: typing.Optional[int] = None) -> int:
    """
    Validates that a port number is valid

    Args:
        port (typing.Union[str, int]): port to validate

    Returns:
        int: port as integer

    Raises:
        exceptions.ValidationException: if port is not valid
    """
    if valid_default is not None and port == valid_default:
        return valid_default
    return validate_numeric(port, min_value=1, max_value=65535, field_name=field_name or 'Port')


def validate_host(host: str, field_name: typing.Optional[str] = None) -> str:
    """
    Validates that a host is valid
    :param host: host to validate
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    try:
        dj_validators.validate_ipv46_address(host)
        return host
    except Exception:
        return validate_fqdn(host, field_name=field_name)


def validate_host_port(host_port_pair: str, field_name: typing.Optional[str] = None) -> tuple[str, int]:
    """
    Validates that a host:port pair is valid
    :param hostPortPair: host:port pair to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    field_name = f' (On field {field_name})' if field_name else ''
    try:
        if '[' in host_port_pair and ']' in host_port_pair:  # IPv6
            host, port = host_port_pair.split(']:')
            host = host[1:]
        else:
            host, port = host_port_pair.split(':')
        # if an ip address is used, it must be valid
        try:
            dj_validators.validate_ipv46_address(host)
            return host, validate_port(port)
        except Exception:
            return validate_hostname(host, 255, False), validate_port(port)
    except Exception:
        raise exceptions.ui.ValidationError(_('{} is not a valid host:port pair').format(host_port_pair + field_name)) from None


def validate_timeout(timeout: 'str|int', field_name: typing.Optional[str] = None) -> int:
    """
    Validates that a timeout value is valid
    :param timeOutStr: timeout to validate
    :param returnAsInteger: if True, returns value as integer, if not, as string
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    return validate_numeric(timeout, min_value=0, field_name=field_name or 'Timeout')


def validate_mac(mac: str, field_name: typing.Optional[str] = None) -> str:
    """
    Validates that a mac address is valid
    :param mac: mac address to validate
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    # Removes white spaces and all to uppercase
    field_name = f' (On field {field_name})' if field_name else ''
    mac = mac.upper().replace(' ', '')

    macRE = re.compile(
        r'^([0-9A-F]{2}[:]){5}([0-9A-F]{2})$'
    )  # In fact, it could be XX-XX-XX-XX-XX-XX, but we use - as range separator

    if macRE.match(mac) is None:
        raise exceptions.ui.ValidationError(_('{} is not a valid MAC address').format(mac + field_name))

    return mac


def validate_mac_range(macRange: str, field_name: typing.Optional[str] = None) -> str:
    """
    Corrects mac range (uppercase, without spaces), and checks that is range is valid
    :param macRange: Range to fix
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    field_name = f' (On field {field_name})' if field_name else ''
    try:
        macRangeStart, macRangeEnd = macRange.split('-')
        validate_mac(macRangeStart)
        validate_mac(macRangeEnd)
    except Exception:
        raise exceptions.ui.ValidationError(_('{} is not a valid MAC range').format(macRange + field_name)) from None

    return macRange


def validate_email(email: str) -> str:
    """
    Validates that an email is valid
    :param email: email to validate
    :return: Raises exceptions.Validation exception if is invalid, else return the value "fixed"
    """
    if len(email) > 254:
        raise exceptions.ui.ValidationError(_('Email address is too long'))

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        raise exceptions.ui.ValidationError(_('Email address is not valid'))

    return email


def validate_basename(basename: str, length: int = -1) -> str:
    """ "Checks if the basename + length is valid for services. Raises an exception if not valid"

    Arguments:
        baseName {str} -- basename to check

    Keyword Arguments:
        length {int} -- length to check, if -1 do not checm (default: {-1})

    Raises:
        exceptions.ValidationException: If anything goes wrong
    Returns:
        None -- [description]
    """
    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]*$', basename) is None:
        raise exceptions.ui.ValidationError(_('The basename is not a valid for a hostname'))

    if length == 0:
        raise exceptions.ui.ValidationError(_('The length of basename plus length must be greater than 0'))

    if length != -1 and len(basename) + length > 15:
        raise exceptions.ui.ValidationError(_('The length of basename plus length must not be greater than 15'))

    if basename.isdigit():
        raise exceptions.ui.ValidationError(_('The machine name can\'t be only numbers'))

    return basename


def validate_json(json_data: typing.Optional[str]) -> typing.Any:
    """
    Validates that a json data is valid (or empty)

    Args:
        jsonData (typing.Optional[str]): Json data to validate

    Raises:
        exceptions.ui.ValidationError: If json data is not valid

    Returns:
        typing.Any: Json data as python object
    """
    if not json_data:
        return None
    try:
        return json.loads(json_data)
    except Exception:
        raise exceptions.ui.ValidationError(_('Invalid JSON data')) from None


def validate_server_certificate(cert: typing.Optional[str]) -> str:
    """
    Validates that a certificate is valid

    Args:
        cert (str): Certificate to validate

    Raises:
        exceptions.ui.ValidationError: If certificate is not valid

    Returns:
        str: Certificate
    """
    if not cert:
        return ''
    try:
        security.is_server_certificate_valid(cert)
    except Exception as e:
        raise exceptions.ui.ValidationError(_('Invalid certificate') + f' :{e}') from e
    return cert


def validate_server_certificate_multiple(value: typing.Optional[str]) -> str:
    """
    Validates the multi line fields refering to attributes
    """
    if not value:
        return ''  # Ok, empty

    pemCerts = value.split('-----END CERTIFICATE-----')
    # Remove empty strings
    pemCerts = [cert for cert in pemCerts if cert.strip() != '']
    # Add back the "-----END CERTIFICATE-----" part
    pemCerts = [cert + '-----END CERTIFICATE-----' for cert in pemCerts]

    for pemCert in pemCerts:
        try:
            load_pem_x509_certificate(pemCert.encode())
        except Exception as e:
            raise exceptions.ui.ValidationError(_('Invalid certificate') + f' :{e}') from e

    return value
