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

import datetime
import logging
import pathlib
import typing

import certifi
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import ExtendedKeyUsageOID

from django.conf import settings

logger = logging.getLogger(__name__)

_SYSTEM_CA_BUNDLE = certifi.where()
_MAX_CHAIN_DEPTH = 10

_CertLoader = typing.Callable[[bytes], list[x509.Certificate]]
_CERT_LOADERS: list[_CertLoader] = [
    x509.load_pem_x509_certificates,
    lambda d: [x509.load_der_x509_certificate(d)],
    lambda d: list(pkcs7.load_pem_pkcs7_certificates(d)),
    lambda d: list(pkcs7.load_der_pkcs7_certificates(d)),
]

_system_trust_cache: list[x509.Certificate] | None = None


def get_server_cert() -> str:
    return getattr(settings, 'RDP_SIGN_CERT', '/etc/certs/server.pem')


def get_server_key() -> str:
    return getattr(settings, 'RDP_SIGN_KEY', '/etc/certs/key.pem')


def load_certificates_any_format(data: bytes) -> list[x509.Certificate]:
    for loader in _CERT_LOADERS:
        try:
            return loader(data)
        except Exception:
            continue
    raise ValueError('Unable to parse certificates (tried PEM, DER, PKCS7)')


def load_private_key_any_format(data: bytes) -> typing.Any:
    for loader in (serialization.load_pem_private_key, serialization.load_der_private_key):
        try:
            return loader(data, password=None, backend=default_backend())
        except Exception:
            continue
    raise ValueError('Unable to parse private key (tried PEM, DER)')


def load_pem_certificates(cert_chain: pathlib.Path | str) -> list[x509.Certificate]:
    return load_certificates_any_format(pathlib.Path(cert_chain).read_bytes())


def load_system_roots() -> list[x509.Certificate]:
    global _system_trust_cache
    if _system_trust_cache is not None:
        return _system_trust_cache
    path = getattr(settings, 'RDP_SIGN_CA_BUNDLE', _SYSTEM_CA_BUNDLE)
    try:
        _system_trust_cache = x509.load_pem_x509_certificates(pathlib.Path(path).read_bytes())
    except Exception as e:
        logger.warning('System CA bundle unavailable at %s: %s', path, e)
        _system_trust_cache = []
    return _system_trust_cache


def _check_leaf_code_signing(leaf: x509.Certificate) -> None:
    # mstsc won't accept the .rdp signature without codeSigning EKU on the leaf
    try:
        eku = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
    except x509.ExtensionNotFound:
        raise ValueError('Leaf missing Extended Key Usage extension (codeSigning required)')
    if ExtendedKeyUsageOID.CODE_SIGNING not in eku:
        raise ValueError('Leaf missing codeSigning EKU required for RDP signing')


def _verify_issued_by(cert: x509.Certificate, issuer: x509.Certificate, label: str) -> None:
    try:
        cert.verify_directly_issued_by(issuer)
    except Exception as e:
        raise ValueError(
            f'{label}: {cert.subject.rfc4514_string()} not issued by '
            f'{issuer.subject.rfc4514_string()}: {e}'
        ) from e


def _walk_chain(leaf: x509.Certificate, chain: list[x509.Certificate]) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    for c in (leaf, *chain):
        if not (c.not_valid_before_utc <= now <= c.not_valid_after_utc):
            raise ValueError(f'Certificate expired or not yet valid: {c.subject.rfc4514_string()}')

    # self-signed leaf with no chain: let it pass but shout about it
    if not chain and leaf.issuer == leaf.subject:
        _verify_issued_by(leaf, leaf, 'Self-signed leaf signature invalid')
        logger.warning(
            'RDP signing certificate is self-signed (subject=%s). mstsc will show '
            '"unknown publisher" unless installed in Windows Trusted Root store.',
            leaf.subject.rfc4514_string(),
        )
        return

    # system CAs + any self-signed root bundled with the leaf both count as anchors
    intermediates: dict[str, x509.Certificate] = {}
    anchors: dict[str, x509.Certificate] = {
        c.subject.rfc4514_string(): c for c in load_system_roots()
    }
    for c in chain:
        (anchors if c.issuer == c.subject else intermediates)[c.subject.rfc4514_string()] = c

    current = leaf
    for _ in range(_MAX_CHAIN_DEPTH):
        issuer_key = current.issuer.rfc4514_string()
        if (anchor := anchors.get(issuer_key)) is not None:
            _verify_issued_by(current, anchor, 'Chain anchor signature invalid')
            return
        if (nxt := intermediates.get(issuer_key)) is None:
            raise ValueError(
                f'Incomplete chain: issuer {issuer_key} not found in intermediates nor system trust store'
            )
        _verify_issued_by(current, nxt, 'Chain link invalid')
        current = nxt

    raise ValueError(f'Chain depth exceeded {_MAX_CHAIN_DEPTH} (possible loop)')


def check_cert_chain(cert_chain: pathlib.Path | str) -> None:
    # preflight hit before signing; raises if anything's off
    certs = load_pem_certificates(cert_chain)
    if not certs:
        raise ValueError('No certificates found in certificate chain')
    _check_leaf_code_signing(certs[0])
    _walk_chain(certs[0], certs[1:])
