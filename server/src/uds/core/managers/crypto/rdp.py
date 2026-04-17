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
# Read key & server from /etc/certs{key,server}.pem (read from config file))
from django.conf import settings

# --- RDP Secure Settings (order matters for mstsc.exe) ---
_RDP_SECURE_SETTINGS = [
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
    ('redirectdrives:i:', 'RedirectDrives'),
    ('redirectprinters:i:', 'RedirectPrinters'),
    ('redirectcomports:i:', 'RedirectCOMPorts'),
    ('redirectsmartcards:i:', 'RedirectSmartCards'),
    ('redirectposdevices:i:', 'RedirectPOSDevices'),
    ('redirectclipboard:i:', 'RedirectClipboard'),
    ('devicestoredirect:s:', 'DevicesToRedirect'),
    ('drivestoredirect:s:', 'DrivesToRedirect'),
    ('loadbalanceinfo:s:', 'LoadBalanceInfo'),
    ('redirectdirectx:i:', 'RedirectDirectX'),
    ('rdgiskdcproxy:i:', 'RDGIsKDCProxy'),
    ('kdcproxyname:s:', 'KDCProxyName'),
    ('eventloguploadaddress:s:', 'EventLogUploadAddress'),
]


import base64
import datetime
import struct
import typing
import logging
from cryptography.hazmat.primitives.serialization import pkcs7, Encoding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.primitives.asymmetric.ec import EllipticCurvePrivateKey

logger = logging.getLogger(__name__)

# PKCS7 signer only supports RSA and EC (DSA/Ed25519 not accepted by pkcs7.add_signer)
_PrivateKey = typing.Union[RSAPrivateKey, EllipticCurvePrivateKey]

# Debian/Ubuntu system CA bundle (populated by update-ca-certificates from
# /usr/share/ca-certificates/). Used to complete chains whose root CA is
# installed in the system trust store rather than bundled in server.pem.
_SYSTEM_CA_BUNDLE = '/etc/ssl/certs/ca-certificates.crt'

_system_trust_cache: typing.Optional[typing.List[x509.Certificate]] = None


def _load_system_trust_store() -> typing.List[x509.Certificate]:
    """
    Load and cache the Debian system CA bundle. Returns [] if missing/unreadable.
    """
    global _system_trust_cache
    if _system_trust_cache is not None:
        return _system_trust_cache
    path = getattr(settings, 'RDP_SIGN_CA_BUNDLE', _SYSTEM_CA_BUNDLE)
    try:
        with open(path, 'rb') as f:
            _system_trust_cache = x509.load_pem_x509_certificates(f.read())
    except (FileNotFoundError, PermissionError) as e:
        logger.warning('System CA bundle unavailable at %s: %s', path, e)
        _system_trust_cache = []
    except Exception as e:
        logger.warning('Unable to parse system CA bundle at %s: %s', path, e)
        _system_trust_cache = []
    return _system_trust_cache

_MAX_CHAIN_DEPTH = 10


def _verify_chain(
    cert: x509.Certificate,
    key: _PrivateKey,
    chain: typing.List[x509.Certificate],
) -> None:
    """
    Validate leaf + chain for RDP signing:
      - Leaf pubkey matches private key.
      - All certs inside validity window (notBefore/notAfter).
      - Leaf has codeSigning EKU (required by mstsc).
      - Chain is built order-independent by subject/issuer lookup: each hop
        verified cryptographically via verify_directly_issued_by.
      - Chain ends at a trust anchor: either a self-signed root bundled in
        server.pem or a CA in the Debian system trust store
        (/etc/ssl/certs/ca-certificates.crt).
      - Self-signed leaf (no chain) is accepted but emits a warning, since
        mstsc clients will show an "unknown publisher" prompt.
    Raises ValueError on any failure.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Leaf pubkey must match private key
    if cert.public_key().public_bytes(
        Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ) != key.public_key().public_bytes(
        Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    ):
        raise ValueError('Leaf certificate public key does not match provided private key')

    # Validity window for leaf + all bundled certs
    for c in [cert, *chain]:
        if not (c.not_valid_before_utc <= now <= c.not_valid_after_utc):
            raise ValueError(
                f'Certificate expired or not yet valid: {c.subject.rfc4514_string()} '
                f'(valid {c.not_valid_before_utc} .. {c.not_valid_after_utc})'
            )

    # Leaf codeSigning EKU (mstsc requires it for .rdp signatures)
    try:
        eku = cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value
        if ExtendedKeyUsageOID.CODE_SIGNING not in eku:
            raise ValueError('Leaf certificate missing codeSigning EKU required for RDP signing')
    except x509.ExtensionNotFound:
        raise ValueError('Leaf certificate missing Extended Key Usage extension (codeSigning required)')

    # Special case: self-signed leaf, no intermediates. Accept with warning.
    if not chain and cert.issuer == cert.subject:
        try:
            cert.verify_directly_issued_by(cert)
        except Exception as e:
            raise ValueError(f'Self-signed leaf signature invalid: {e}') from e
        logger.warning(
            'RDP signing certificate is self-signed (subject=%s). '
            'mstsc clients will show an "unknown publisher" warning unless the '
            'certificate is manually installed in the Windows Trusted Root store.',
            cert.subject.rfc4514_string(),
        )
        return

    # Split bundled chain into intermediates and self-signed bundled roots.
    # Bundled self-signed roots act as extra trust anchors (useful for
    # private/offline CAs not installed in the system store).
    intermediates: typing.Dict[str, x509.Certificate] = {}
    bundled_roots: typing.Dict[str, x509.Certificate] = {}
    for c in chain:
        subject_key = c.subject.rfc4514_string()
        if c.issuer == c.subject:
            bundled_roots[subject_key] = c
        else:
            intermediates[subject_key] = c

    # Trust anchor index: system store + bundled roots (bundled override).
    trust_anchors: typing.Dict[str, x509.Certificate] = {
        c.subject.rfc4514_string(): c for c in _load_system_trust_store()
    }
    trust_anchors.update(bundled_roots)

    # Walk: leaf → intermediate → ... → trust anchor. Crypto-verify each hop.
    current = cert
    for _ in range(_MAX_CHAIN_DEPTH):
        issuer_key = current.issuer.rfc4514_string()

        anchor = trust_anchors.get(issuer_key)
        if anchor is not None:
            try:
                current.verify_directly_issued_by(anchor)
            except Exception as e:
                raise ValueError(
                    f'Chain anchor signature invalid: {current.subject.rfc4514_string()} '
                    f'not validly issued by trust anchor {anchor.subject.rfc4514_string()}: {e}'
                ) from e
            if anchor.issuer == anchor.subject:
                try:
                    anchor.verify_directly_issued_by(anchor)
                except Exception as e:
                    raise ValueError(
                        f'Trust anchor {anchor.subject.rfc4514_string()} self-signature invalid: {e}'
                    ) from e
            return

        nxt = intermediates.get(issuer_key)
        if nxt is not None:
            try:
                current.verify_directly_issued_by(nxt)
            except Exception as e:
                raise ValueError(
                    f'Chain link invalid: {current.subject.rfc4514_string()} not '
                    f'validly issued by {nxt.subject.rfc4514_string()}: {e}'
                ) from e
            current = nxt
            continue

        raise ValueError(
            f'Incomplete CA chain: issuer {current.issuer.rfc4514_string()} '
            f'of {current.subject.rfc4514_string()} not found in bundled '
            f'intermediates nor in system trust store'
        )

    raise ValueError(f'Chain depth exceeded {_MAX_CHAIN_DEPTH} (possible loop)')


def _load_cert_key_chain() -> typing.Tuple[x509.Certificate, typing.Any, typing.List[x509.Certificate]]:
    """
    Load certificate, private key and chain from global configuration.
    Uses cryptography.x509.load_pem_x509_certificates to robustly parse
    all CERTIFICATE blocks regardless of surrounding content (keys, text,
    trusted-certificate blocks, RSA/EC markers, etc).
    Validates the chain before returning.
    """
    server_pem_path = getattr(settings, 'RDP_SIGN_CERT', '/etc/certs/server.pem')
    key_pem_path = getattr(settings, 'RDP_SIGN_KEY', '/etc/certs/key.pem')

    with open(server_pem_path, 'rb') as f:
        pem_data = f.read()

    try:
        certs = x509.load_pem_x509_certificates(pem_data)
    except Exception as e:
        raise ValueError(f'Unable to parse certificates from {server_pem_path}: {e}') from e

    if not certs:
        raise ValueError(f'No certificates found in {server_pem_path}')

    cert, chain = certs[0], certs[1:]

    with open(key_pem_path, 'rb') as f:
        key_pem = f.read()
    raw_key = serialization.load_pem_private_key(key_pem, password=None, backend=default_backend())
    if not isinstance(raw_key, (RSAPrivateKey, EllipticCurvePrivateKey)):
        raise ValueError(
            f'Unsupported private key type for RDP signing: {type(raw_key).__name__} '
            f'(expected RSA or EC; PKCS7 signer does not accept DSA/DH/Ed25519)'
        )
    key: _PrivateKey = raw_key

    _verify_chain(cert, key, chain)
    return cert, key, chain

def sign_rdp_settings(
    settings_lines: typing.List[str],
    cert: typing.Optional[x509.Certificate] = None,
    key: typing.Optional[_PrivateKey] = None,
    chain: typing.Optional[typing.List[x509.Certificate]] = None,
) -> typing.Tuple[str, typing.List[str]]:
    """
    Sign the RDP configuration lines and return (base64_signature, signnames).
    """
    # Filter and order the lines to sign
    signlines: typing.List[str] = []
    signnames: typing.List[str] = []
    for k, name in _RDP_SECURE_SETTINGS:
        for line in settings_lines:
            if line.startswith(k):
                signnames.append(name)
                signlines.append(line)

    msgtext = '\r\n'.join(signlines) + '\r\nsignscope:s:' + ','.join(signnames) + '\r\n' + '\x00'
    msgblob = msgtext.encode('utf-16le')

    if cert is None or key is None:
        cert, key, chain = _load_cert_key_chain()
    assert cert is not None and key is not None  # narrow for type checker

    # Use PKCS7 to sign, including the chain if present
    builder = pkcs7.PKCS7SignatureBuilder().set_data(msgblob)
    builder = builder.add_signer(cert, key, hashes.SHA256())
    if chain:
        for c in chain:
            builder = builder.add_certificate(c)
    signature = builder.sign(Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary])

    # Add 12-byte header as rdpsign.exe does
    msgsig = struct.pack('<I', 0x00010001)
    msgsig += struct.pack('<I', 0x00000001)
    msgsig += struct.pack('<I', len(signature))
    msgsig += signature

    sigval = base64.b64encode(msgsig).decode('ascii')
    return sigval, signnames

def sign_rdp(
    rdp_text: str,
    cert: typing.Optional[x509.Certificate] = None,
    key: typing.Optional[_PrivateKey] = None,
    chain: typing.Optional[typing.List[x509.Certificate]] = None,
) -> str:
    """
    Sign a complete RDP file (text) and return the resulting .rdp with
    the signscope:s: and signature:s: lines appended at the end.
    """
    # Strip previous signature and signscope lines and empty lines
    lines = [
        l.strip()
        for l in rdp_text.splitlines()
        if l.strip() and not l.startswith('signature:s:') and not l.startswith('signscope:s:')
    ]
    # If alternate full address is missing, add it
    fulladdress = None
    alternatefulladdress = None
    for l in lines:
        if l.startswith('full address:s:'):
            fulladdress = l[15:]
        elif l.startswith('alternate full address:s:'):
            alternatefulladdress = l[25:]
    if fulladdress and not alternatefulladdress:
        lines.append('alternate full address:s:' + fulladdress)

    sigval, signnames = sign_rdp_settings(lines, cert, key, chain)
    lines.append('signscope:s:' + ','.join(signnames))
    lines.append('signature:s:' + sigval)
    return '\r\n'.join(lines) + '\r\n'
