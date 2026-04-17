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
import struct
import typing
import logging
from cryptography.hazmat.primitives.serialization import pkcs7, Encoding
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509

logger = logging.getLogger(__name__)

def _load_cert_key_chain():
    """
    Load certificate, key and chain from global configuration.
    """
    server_pem_path = getattr(settings, 'RDP_SIGN_CERT', '/etc/certs/server.pem')
    key_pem_path = getattr(settings, 'RDP_SIGN_KEY', '/etc/certs/key.pem')
    with open(server_pem_path, 'r') as f:
        pem_data = f.read()
    # Split all certificate blocks
    cert_blocks = pem_data.split('-----END CERTIFICATE-----')
    certs = []
    for block in cert_blocks:
        block = block.strip()
        if block:
            block += '\n-----END CERTIFICATE-----\n'
            certs.append(block)
    if not certs:
        raise ValueError("No certificates found in server.pem")
    # First block is the leaf, the rest is the chain
    cert = x509.load_pem_x509_certificate(certs[0].encode(), default_backend())
    chain = [x509.load_pem_x509_certificate(c.encode(), default_backend()) for c in certs[1:]] if len(certs) > 1 else []
    with open(key_pem_path, 'rb') as f:
        key_pem = f.read()
    key = serialization.load_pem_private_key(key_pem, password=None, backend=default_backend())
    return cert, key, chain

def sign_rdp_settings(settings_lines: typing.List[str], cert=None, key=None, chain=None) -> typing.Tuple[str, typing.List[str]]:
    """
    Sign the RDP configuration lines and return (base64_signature, signnames).
    """
    # Filter and order the lines to sign
    signlines = []
    signnames = []
    for k, name in _RDP_SECURE_SETTINGS:
        for line in settings_lines:
            if line.startswith(k):
                signnames.append(name)
                signlines.append(line)

    msgtext = '\r\n'.join(signlines) + '\r\nsignscope:s:' + ','.join(signnames) + '\r\n' + '\x00'
    msgblob = msgtext.encode('utf-16le')

    if cert is None or key is None:
        cert, key, chain = _load_cert_key_chain()

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

def sign_rdp(rdp_text: str, cert=None, key=None, chain=None) -> str:
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
