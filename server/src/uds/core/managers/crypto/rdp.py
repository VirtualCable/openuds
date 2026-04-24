# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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

import base64
import logging
import struct

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7, pkcs12

from . import certs as _certs

logger = logging.getLogger(__name__)

# PKCS7 add_signer rejects DSA/Ed25519
_PrivateKey = RSAPrivateKey | EllipticCurvePrivateKey

# order matters, mstsc reads signscope in this exact order
_RDP_SECURE_SETTINGS: list[tuple[str, str]] = [
    ('full address:s:', 'Full Address'),
    ('alternate full address:s:', 'Alternate Full Address'),
    ('pcb:s:', 'PCB'),
    ('use redirection server name:i:', 'Use Redirection Server Name'),
    ('server port:i:', 'Server Port'),
    ('negotiate security layer:i:', 'Negotiate Security Layer'),
    ('enablecredsspsupport:i:', 'EnableCredSspSupport'),
    ('disableconnectionsharing:i:', 'DisableConnectionSharing'),
    ('autoreconnection enabled:i:', 'AutoReconnection Enabled'),
    ('gatewayhostname:s:', 'GatewayHostname'),
    ('gatewayusagemethod:i:', 'GatewayUsageMethod'),
    ('gatewayprofileusagemethod:i:', 'GatewayProfileUsageMethod'),
    ('gatewaycredentialssource:i:', 'GatewayCredentialsSource'),
    ('support url:s:', 'Support URL'),
    ('promptcredentialonce:i:', 'PromptCredentialOnce'),
    ('require pre-authentication:i:', 'Require pre-authentication'),
    ('pre-authentication server address:s:', 'Pre-authentication server address'),
    ('alternate shell:s:', 'Alternate Shell'),
    ('shell working directory:s:', 'Shell Working Directory'),
    ('remoteapplicationprogram:s:', 'RemoteApplicationProgram'),
    ('remoteapplicationexpandworkingdir:s:', 'RemoteApplicationExpandWorkingdir'),
    ('remoteapplicationmode:i:', 'RemoteApplicationMode'),
    ('remoteapplicationguid:s:', 'RemoteApplicationGuid'),
    ('remoteapplicationname:s:', 'RemoteApplicationName'),
    ('remoteapplicationicon:s:', 'RemoteApplicationIcon'),
    ('remoteapplicationfile:s:', 'RemoteApplicationFile'),
    ('remoteapplicationfileextensions:s:', 'RemoteApplicationFileExtensions'),
    ('remoteapplicationcmdline:s:', 'RemoteApplicationCmdLine'),
    ('remoteapplicationexpandcmdline:s:', 'RemoteApplicationExpandCmdLine'),
    ('prompt for credentials:i:', 'Prompt For Credentials'),
    ('authentication level:i:', 'Authentication Level'),
    ('audiomode:i:', 'AudioMode'),
    ('audiocapturemode:i:', 'AudioCaptureMode'),
    ('redirectdrives:i:', 'RedirectDrives'),
    ('redirectprinters:i:', 'RedirectPrinters'),
    ('redirectcomports:i:', 'RedirectCOMPorts'),
    ('redirectsmartcards:i:', 'RedirectSmartCards'),
    ('redirectposdevices:i:', 'RedirectPOSDevices'),
    ('redirectclipboard:i:', 'RedirectClipboard'),
    ('devicestoredirect:s:', 'DevicesToRedirect'),
    ('drivestoredirect:s:', 'DrivesToRedirect'),
    ('camerastoredirect:s:', 'CamerasToRedirect'),
    ('loadbalanceinfo:s:', 'LoadBalanceInfo'),
    ('redirectdirectx:i:', 'RedirectDirectX'),
    ('rdgiskdcproxy:i:', 'RDGIsKDCProxy'),
    ('kdcproxyname:s:', 'KDCProxyName'),
    ('eventloguploadaddress:s:', 'EventLogUploadAddress'),
]


def _ensure_signer_key(key: object) -> _PrivateKey:
    if not isinstance(key, (RSAPrivateKey, EllipticCurvePrivateKey)):
        raise ValueError(
            f'Unsupported private key type for RDP signing: {type(key).__name__} '
            f'(expected RSA or EC; PKCS7 rejects DSA/DH/Ed25519)'
        )
    return key


def _check_pubkey_matches_key(cert: x509.Certificate, key: _PrivateKey) -> None:
    fmt = serialization.PublicFormat.SubjectPublicKeyInfo
    if cert.public_key().public_bytes(Encoding.DER, fmt) != key.public_key().public_bytes(Encoding.DER, fmt):
        raise ValueError('Leaf certificate public key does not match provided private key')


def _load_cert_key_chain() -> tuple[x509.Certificate, _PrivateKey, list[x509.Certificate]]:
    cert_path = _certs.get_server_cert()
    with open(cert_path, 'rb') as f:
        cert_data = f.read()

    # try PFX first, it carries key+chain in one file
    try:
        p12_key, p12_cert, p12_chain = pkcs12.load_key_and_certificates(cert_data, password=None)
    except Exception:
        p12_key = p12_cert = None
        p12_chain = []

    if p12_cert is not None and p12_key is not None:
        key = _ensure_signer_key(p12_key)
        _certs.check_chain(p12_cert, list(p12_chain or []))
        _check_pubkey_matches_key(p12_cert, key)
        return p12_cert, key, list(p12_chain or [])

    certs = _certs.load_certificates_any_format(cert_data)
    if not certs:
        raise ValueError(f'No certificates found in {cert_path}')

    with open(_certs.get_server_key(), 'rb') as f:
        key_data = f.read()
    key = _ensure_signer_key(_certs.load_private_key_any_format(key_data))

    _certs.check_cert_chain(cert_path)
    _check_pubkey_matches_key(certs[0], key)
    return certs[0], key, certs[1:]


def sign_rdp_settings(
    settings_lines: list[str],
    cert: x509.Certificate | None = None,
    key: _PrivateKey | None = None,
    chain: list[x509.Certificate] | None = None,
) -> tuple[str, list[str]]:
    signlines: list[str] = []
    signnames: list[str] = []
    for prefix, name in _RDP_SECURE_SETTINGS:
        for line in settings_lines:
            if line.startswith(prefix):
                signnames.append(name)
                signlines.append(line)

    msgblob = (
        '\r\n'.join(signlines) + '\r\nsignscope:s:' + ','.join(signnames) + '\r\n\x00'
    ).encode('utf-16le')

    if cert is None or key is None:
        cert, key, chain = _load_cert_key_chain()

    builder = pkcs7.PKCS7SignatureBuilder().set_data(msgblob).add_signer(cert, key, hashes.SHA256())
    for c in chain or []:
        builder = builder.add_certificate(c)
    signature = builder.sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])

    # rdpsign.exe prepends this 12-byte header; first 8 bytes are magic, nobody knows what they mean
    msgsig = struct.pack('<III', 0x00010001, 0x00000001, len(signature)) + signature
    return base64.b64encode(msgsig).decode('ascii'), signnames


def sign_rdp(
    rdp_text: str,
    cert: x509.Certificate | None = None,
    key: _PrivateKey | None = None,
    chain: list[x509.Certificate] | None = None,
) -> str:
    # strip any previous signature/signscope and blank lines
    lines = [
        s for s in (l.strip() for l in rdp_text.splitlines())
        if s and not s.startswith(('signature:s:', 'signscope:s:'))
    ]

    # mirror full address into alternate, otherwise it's a tampering hole
    full = alt = None
    for l in lines:
        if l.startswith('full address:s:'):
            full = l[15:]
        elif l.startswith('alternate full address:s:'):
            alt = l[25:]
    if full and not alt:
        lines.append('alternate full address:s:' + full)

    sigval, signnames = sign_rdp_settings(lines, cert, key, chain)
    lines.append('signscope:s:' + ','.join(signnames))
    lines.append('signature:s:' + sigval)
    return '\r\n'.join(lines) + '\r\n'
