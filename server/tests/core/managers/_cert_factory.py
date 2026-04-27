# -*- coding: utf-8 -*-
#
# Copyright (c) 2026 Virtual Cable S.L.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# Cert/key helpers for crypto manager tests. Underscore prefix keeps pytest from collecting it.
import datetime
import pathlib
import secrets
import tempfile
import typing

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.x509.oid import NameOID

from django.test import override_settings

from uds.core.managers.crypto import certs as _certs

from ...utils.test import UDSTestCase

_PrivateKey = typing.Union[RSAPrivateKey, ec.EllipticCurvePrivateKey]

# 1024 here only because keygen dominates test runtime; not for production
_TEST_RSA_BITS = 1024


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def make_rsa_key(size: int = _TEST_RSA_BITS) -> RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=size)



def build_cert(
    subject_name: x509.Name,
    subject_key: _PrivateKey,
    issuer_name: x509.Name,
    issuer_key: _PrivateKey,
    *,
    is_ca: bool = False,
    not_before: typing.Optional[datetime.datetime] = None,
    not_after: typing.Optional[datetime.datetime] = None,
) -> x509.Certificate:
    now = datetime.datetime.now(datetime.timezone.utc)
    nb = not_before or (now - datetime.timedelta(days=1))
    na = not_after or (now + datetime.timedelta(days=365))
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject_name)
        .issuer_name(issuer_name)
        .public_key(subject_key.public_key())
        .serial_number(secrets.randbits(63))
        .not_valid_before(nb)
        .not_valid_after(na)
    )
    if is_ca:
        builder = builder.add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
    return builder.sign(issuer_key, hashes.SHA256())


def self_signed(
    cn: str,
    *,
    key: typing.Optional[_PrivateKey] = None,
    is_ca: bool = True,
    not_before: typing.Optional[datetime.datetime] = None,
    not_after: typing.Optional[datetime.datetime] = None,
) -> tuple[x509.Certificate, _PrivateKey]:
    key = key or make_rsa_key()
    name = _name(cn)
    cert = build_cert(name, key, name, key, is_ca=is_ca, not_before=not_before, not_after=not_after)
    return cert, key


def issue(
    cn: str,
    issuer_cert: x509.Certificate,
    issuer_key: _PrivateKey,
    *,
    key: typing.Optional[_PrivateKey] = None,
    is_ca: bool = False,
    not_before: typing.Optional[datetime.datetime] = None,
    not_after: typing.Optional[datetime.datetime] = None,
) -> tuple[x509.Certificate, _PrivateKey]:
    key = key or make_rsa_key()
    cert = build_cert(
        _name(cn),
        key,
        issuer_cert.subject,
        issuer_key,
        is_ca=is_ca,
        not_before=not_before,
        not_after=not_after,
    )
    return cert, key


def to_pem(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def to_der(cert: x509.Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.DER)


def key_to_pem(key: _PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def key_to_der(key: _PrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def chain_to_pem(*certs: x509.Certificate) -> bytes:
    return b''.join(to_pem(c) for c in certs)


class CertTestCase(UDSTestCase):
    _tmpdir: tempfile.TemporaryDirectory[str]
    tmp: pathlib.Path

    def setUp(self) -> None:
        super().setUp()
        _certs._system_trust_cache = None  # type: ignore[attr-defined]
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmpdir.name)

    def tearDown(self) -> None:
        _certs._system_trust_cache = None  # type: ignore[attr-defined]
        self._tmpdir.cleanup()
        super().tearDown()

    def write(self, name: str, data: bytes) -> pathlib.Path:
        p = self.tmp / name
        p.write_bytes(data)
        return p

    def install_trust(self, *roots: x509.Certificate) -> None:
        bundle = self.write('trust.pem', chain_to_pem(*roots))
        ov = override_settings(RDP_SIGN_CA_BUNDLE=str(bundle))
        ov.enable()
        self.addCleanup(ov.disable)
