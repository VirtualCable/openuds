# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2024 Virtual Cable S.L.U.
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
# pyright: reportArgumentType=false
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import ipaddress
import logging
import random
import secrets
import ssl
import typing
import datetime

import certifi
import requests
import requests.adapters
import urllib3
import urllib3.exceptions
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from django.conf import settings

from uds.core import consts

logger = logging.getLogger(__name__)

KEY_SIZE = 4096
SECRET_SIZE = 32

# Disable warnings from urllib for
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    # Ensure that we do not get warnings about self signed certificates and so
    import requests.packages.urllib3  # type: ignore

    requests.packages.urllib3.disable_warnings()  # pyright: ignore
except Exception:  # nosec: simple check for disabling warnings,
    # Igonre if we cannot disable warnings
    pass


def create_self_signed_cert(ip: str) -> tuple[str, str, str]:
    """
    Generates a self signed certificate for the given ip.
    This method is mainly intended to be used for generating/saving Actor certificates.
    UDS will check that actor server certificate is the one generated by this method.
    """
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=KEY_SIZE,
        backend=default_backend(),
    )
    # Create a random password for private key
    password = secrets.token_hex(SECRET_SIZE)

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))])

    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self signed, its Issuer DN must match its Subject DN.
        .public_key(key.public_key())
        .serial_number(random.SystemRandom().randint(0, 1 << 64))
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=10 * 365))
        .add_extension(basic_contraints, False)
        .add_extension(san, False)
        .sign(key, hashes.SHA256(), default_backend())
    )

    return (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.BestAvailableEncryption(password.encode()),
        ).decode(),
        cert.public_bytes(encoding=serialization.Encoding.PEM).decode(),
        password,
    )


def create_client_sslcontext(verify: bool = True) -> ssl.SSLContext:
    """
    Creates a SSLContext for client connections.

    Args:
        verify: If True, the server certificate will be verified. (Default: True)

    Returns:
        A SSLContext object.
    """
    ssl_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH, cafile=certifi.where())
    if not verify:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.VerifyMode.CERT_NONE

    # Disable TLS1.0 and TLS1.1, SSLv2 and SSLv3 are disabled by default
    # Next line is deprecated in Python 3.7
    # sslContext.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 | ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3
    if hasattr(settings, 'SECURE_MIN_TLS_VERSION') and settings.SECURE_MIN_TLS_VERSION:
        # format is "1.0, 1.1, 1.2 or 1.3", convert to ssl.TLSVersion.TLSv1_0, ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_2 or ssl.TLSVersion.TLSv1_3
        ssl_context.minimum_version = getattr(
            ssl.TLSVersion, 'TLSv' + settings.SECURE_MIN_TLS_VERSION.replace('.', '_')
        )
    else:
        ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    ssl_context.maximum_version = ssl.TLSVersion.MAXIMUM_SUPPORTED
    if hasattr(settings, 'SECURE_CIPHERS') and settings.SECURE_CIPHERS:
        ssl_context.set_ciphers(settings.SECURE_CIPHERS)

    return ssl_context


def check_certificate_matches_private_key(*, cert: str, key: str) -> bool:
    """
    Checks if a certificate and a private key match.
    All parameters must be keyword arguments.
    Borh must be in PEM format.
    """
    try:
        public_cert = (
            x509.load_pem_x509_certificate(cert.encode(), default_backend())
            .public_key()
            .public_bytes(
                format=serialization.PublicFormat.PKCS1,
                encoding=serialization.Encoding.PEM,
            )
        )
        public_key = (
            serialization.load_pem_private_key(key.encode(), password=None, backend=default_backend())
            .public_key()
            .public_bytes(
                format=serialization.PublicFormat.PKCS1,
                encoding=serialization.Encoding.PEM,
            )
        )
        return public_cert == public_key
    except Exception:
        # Not intended to show kind of error, just to return False if the certificate does not match the key
        # Even if the key or certificate is not valid, we only want a True if they match, False otherwise
        return False


def secure_requests_session(*, verify: typing.Union[str, bool] = True) -> 'requests.Session':
    '''
    Generates a requests.Session object with a custom adapter that uses a custom SSLContext.
    This is intended to be used for requests that need to be secure, but not necessarily verified.
    Removes the support for TLS1.0 and TLS1.1, and disables SSLv2 and SSLv3. (done in @createClientSslContext)

    Args:
        verify: If True, the server certificate will be verified. (Default: True)

    Returns:
        A requests.Session object.
    '''

    # Copy verify value
    lverify = verify

    # Disable warnings from urllib for insecure requests
    # Note that although this is done globaly, on some circunstances, may be overriden later
    # This will ensure that we do not get warnings about self signed certificates
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    class UDSHTTPAdapter(requests.adapters.HTTPAdapter):
        _ssl_context: ssl.SSLContext

        def init_poolmanager(self, *args: typing.Any, **kwargs: typing.Any) -> None:
            self._ssl_context = kwargs["ssl_context"] = create_client_sslcontext(verify=verify is True)

            # See urllib3.poolmanager.SSL_KEYWORDS for all available keys.
            return super().init_poolmanager(*args, **kwargs)  # type: ignore

        def cert_verify(self, conn: typing.Any, url: typing.Any, verify: 'str|bool', cert: typing.Any) -> None:
            """Verify a SSL certificate. This method should not be called from user
            code, and is only exposed for use when subclassing the HTTPAdapter class
            """

            # If lverify is an string, use it even if verify is False
            # if not, use verify value
            if not isinstance(verify, str):
                verify = lverify

            # 2.32  version of requests, broke the hability to override the ssl_context
            # Please, ensure that you are using a version of requests that is compatible with this code (2.32.3) or newer
            # And this way, our ssl_context is not used, so we need to override it again to ensure that our ssl_context is used
            # if 'conn_kw' in conn.__dict__:
            #     conn_kw = conn.__dict__['conn_kw']
            #     conn_kw['ssl_context'] = self.ssl_context

            super().cert_verify(conn, url, verify, cert)  # type: ignore

    session = requests.Session()
    session.mount("https://", UDSHTTPAdapter())

    # Add user agent header to session
    session.headers.update({"User-Agent": consts.system.USER_AGENT})

    return session


def is_server_certificate_valid(cert: str) -> bool:
    """
    Checks if a certificate is valid.
    All parameters must be keyword arguments.
    Borh must be in PEM format.
    """
    try:
        x509.load_pem_x509_certificate(cert.encode(), default_backend())
        return True
    except Exception:
        return False


def is_private_key_valid(key: str) -> bool:
    """
    Checks if a private key is valid.
    All parameters must be keyword arguments.
    Borh must be in PEM format.
    """
    try:
        serialization.load_pem_private_key(key.encode(), password=None, backend=default_backend())
        return True
    except Exception:
        return False
