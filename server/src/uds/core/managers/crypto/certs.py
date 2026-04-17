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

import logging
import pathlib
import typing

import certifi
from cryptography import x509
from cryptography.x509 import load_pem_x509_certificates, NameOID

from django.conf import settings

logger = logging.getLogger(__name__)


def get_server_cert() -> str:
    # Get server cert from settings
    return getattr(settings, 'RDP_SIGN_CERT', '/etc/certs/server.pem')


def get_server_key() -> str:
    # Get server key from settings
    return getattr(settings, 'RDP_SIGN_KEY', '/etc/certs/key.pem')


def load_pem_certificates(cert_chain: pathlib.Path | str) -> list[x509.Certificate]:
    if isinstance(cert_chain, pathlib.Path):
        with cert_chain.open('rb') as f:
            pem_data = f.read()
    else:
        pem_data = cert_chain.encode('utf-8')

    try:
        return load_pem_x509_certificates(pem_data)
    except Exception as e:
        raise ValueError(f'Unable to parse certificate chain: {e}') from e


def load_system_roots(ca_path: str) -> dict[str, x509.Certificate]:
    """
    Load trusted root certificates from the system store.
    Returns a dict mapping subject RFC4514 string -> Certificate.
    """
    ca_file = pathlib.Path(ca_path)
    if not ca_file.exists():
        print(f"⚠  CA file not found: {ca_path}")
        return {}

    pem_data = ca_file.read_bytes()
    certs = load_pem_x509_certificates(pem_data)

    # Index by subject for quick lookup
    roots: dict[str, x509.Certificate] = {}
    for cert in certs:
        key = cert.subject.rfc4514_string()
        roots[key] = cert

    return roots


def cert_name(cert: x509.Certificate) -> str:
    try:
        cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn:
            return cn[0].rfc4514_string()
    except Exception:
        pass
    return cert.subject.rfc4514_string()


def cert_issuer_name(cert: x509.Certificate) -> str:
    try:
        cn = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn:
            return cn[0].rfc4514_string()
    except Exception:
        pass
    return cert.issuer.rfc4514_string()


def build_chain(
    leaf: x509.Certificate,
    intermediates: list[x509.Certificate],
    trusted_roots: dict[str, x509.Certificate],
) -> tuple[list[x509.Certificate], x509.Certificate | None, list[str]]:
    chain: list[x509.Certificate] = [leaf]
    errors: list[str] = []
    current = leaf

    intermediate_map: dict[str, x509.Certificate] = {
        cert.subject.rfc4514_string(): cert for cert in intermediates
    }

    MAX_DEPTH: typing.Final[int] = 10
    for _ in range(MAX_DEPTH):
        issuer_key = current.issuer.rfc4514_string()

        if issuer_key in trusted_roots:
            return chain, trusted_roots[issuer_key], errors

        next_cert = intermediate_map.get(issuer_key)
        if next_cert is not None:
            chain.append(next_cert)
            current = next_cert
            continue

        errors.append(f'Missing certificate for issuer: {cert_issuer_name(current)}')
        errors.append(f'   (needed to verify: {cert_name(current)})')
        return chain, None, errors

    errors.append('Chain too deep (possible loop)')
    return chain, None, errors


def check_cert_chain(cert_chain: pathlib.Path | str) -> None:
    certs = load_pem_certificates(cert_chain)
    if not certs:
        raise ValueError('No certificates found in certificate chain')

    logger.debug('check_cert_chain: loaded %d certificates', len(certs))

    leaf = certs[0]
    chain = certs[1:]
    trusted_roots = load_system_roots(certifi.where())

    _, trusted_root, errors = build_chain(leaf, chain, trusted_roots)
    if trusted_root is None:
        raise ValueError(errors[0] if errors else 'Certificate chain incomplete')

    logger.debug('check_cert_chain: certificate chain validated successfully')
