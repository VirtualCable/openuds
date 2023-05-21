# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import secrets
import random
import datetime
import tempfile
import ipaddress
import typing
import ssl
import os
import contextlib

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def selfSignedCert(ip: str, use_password: bool = True) -> typing.Tuple[str, str, str]:
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    # Create a random password for private key
    password = secrets.token_urlsafe(32)

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, ip)])
    san = x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))])

    basic_contraints = x509.BasicConstraints(ca=True, path_length=0)
    now = datetime.datetime.utcnow()
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
    args: typing.Dict[str, typing.Any] = {
        'encoding': serialization.Encoding.PEM,
        'format': serialization.PrivateFormat.TraditionalOpenSSL,
    }
    if use_password:
        args['encryption_algorithm'] = serialization.BestAvailableEncryption(password.encode())
    else:
        args['encryption_algorithm'] = serialization.NoEncryption()
    return (
        key.private_bytes(**args
        ).decode(),
        cert.public_bytes(encoding=serialization.Encoding.PEM).decode(),
        password,
    )


def sslContext() -> typing.Tuple[ssl.SSLContext, str, str]:  # pylint: disable=unused-argument
    """Returns an ssl context an the certificate & password for an ip

    Args:
        ip (str): Ip for subject name

    Returns:
        typing.Tuple[ssl.SSLContext, str, str]: ssl context, certificate file and password
        
    """
    # First, create server cert and key on temp dir
    tmpdir = tempfile.gettempdir()
    tmpname = secrets.token_urlsafe(32)
    cert, key, password = selfSignedCert('127.0.0.1')
    cert_file = f'{tmpdir}/{tmpname}.pem'
    with open(cert_file, 'w', encoding='utf-8') as f:
        f.write(key)
        f.write(cert)
    # Create SSL context
    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_ctx.load_cert_chain(certfile=f'{tmpdir}/{tmpname}.pem', password=password)
    ssl_ctx.check_hostname = False
    ssl_ctx.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384')

    return ssl_ctx, cert_file, password

@contextlib.contextmanager
def ssl_context() -> typing.Generator[typing.Tuple[ssl.SSLContext, str], None, None]:
    """Returns an ssl context for an ip

    Args:
        ip (str): Ip for subject name

    Returns:
        ssl.SSLContext: ssl context
    """
    # First, create server cert and key on temp dir
    ssl_ctx, cert_file, password = sslContext()  # pylint: disable=unused-variable

    yield ssl_ctx, cert_file

    # Remove cert file
    os.remove(cert_file)
