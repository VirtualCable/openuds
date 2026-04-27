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
import base64
import struct

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519
from cryptography.hazmat.primitives.serialization import pkcs12

from django.test import override_settings

from uds.core.managers.crypto import rdp

from . import _cert_factory as cf


class RdpTest(cf.CertTestCase):
    # ------------------------------------------------------------------ signer key guard
    def test_ensure_signer_key_rejects_unsupported(self) -> None:
        ed_key = ed25519.Ed25519PrivateKey.generate()
        dsa_key = dsa.generate_private_key(key_size=2048)
        for label, k in (('ed25519', ed_key), ('dsa', dsa_key)):
            with self.subTest(kind=label):
                with self.assertRaises(ValueError) as ctx:
                    rdp._ensure_signer_key(k)
                self.assertIn('Unsupported private key type', str(ctx.exception))

    def test_ensure_signer_key_accepts_rsa_and_ec(self) -> None:
        rsa_key = cf.make_rsa_key()
        ec_key = ec.generate_private_key(ec.SECP256R1())
        for label, k in (('rsa', rsa_key), ('ec', ec_key)):
            with self.subTest(kind=label):
                self.assertIs(rdp._ensure_signer_key(k), k)

    # ------------------------------------------------------------------ pubkey match
    def test_pubkey_match_ok(self) -> None:
        cert, key = cf.self_signed('MATCH', is_ca=False)
        rdp._check_pubkey_matches_key(cert, key)

    def test_pubkey_match_mismatch_raises(self) -> None:
        cert, _ = cf.self_signed('MATCH', is_ca=False)
        other_key = cf.make_rsa_key()
        with self.assertRaises(ValueError) as ctx:
            rdp._check_pubkey_matches_key(cert, other_key)
        self.assertIn('does not match', str(ctx.exception))

    # ------------------------------------------------------------------ sign_rdp_settings
    def test_sign_rdp_settings_preserves_declared_order(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        lines = [
            'audiomode:i:0',
            'full address:s:host.example.com',
            'server port:i:3389',
        ]
        sig_b64, signnames = rdp.sign_rdp_settings(lines, cert=cert, key=key, chain=[])
        self.assertEqual(signnames, ['Full Address', 'Server Port', 'AudioMode'])

        raw = base64.b64decode(sig_b64)
        self.assertGreater(len(raw), 12)
        magic, one, siglen = struct.unpack('<III', raw[:12])
        self.assertEqual(magic, 0x00010001)
        self.assertEqual(one, 0x00000001)
        self.assertEqual(siglen, len(raw) - 12)

    def test_sign_rdp_settings_ignores_unknown_lines(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        lines = ['unknown:s:whatever', 'full address:s:host']
        _, signnames = rdp.sign_rdp_settings(lines, cert=cert, key=key, chain=[])
        self.assertEqual(signnames, ['Full Address'])

    # ------------------------------------------------------------------ sign_rdp
    def test_sign_rdp_appends_signscope_and_signature(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        rdp_text = 'full address:s:host.example.com\r\nserver port:i:3389\r\n'
        signed = rdp.sign_rdp(rdp_text, cert=cert, key=key, chain=[])
        out_lines = signed.splitlines()
        signscope = next(l for l in out_lines if l.startswith('signscope:s:'))
        signature = next(l for l in out_lines if l.startswith('signature:s:'))
        self.assertIn('Full Address', signscope)
        self.assertIn('Server Port', signscope)
        self.assertTrue(signature.startswith('signature:s:'))
        base64.b64decode(signature[len('signature:s:'):])

    def test_sign_rdp_strips_previous_signature_lines(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        rdp_text = (
            'full address:s:host\r\n'
            'signscope:s:Full Address\r\n'
            'signature:s:OLDBOGUS==\r\n'
        )
        signed = rdp.sign_rdp(rdp_text, cert=cert, key=key, chain=[])
        self.assertEqual(signed.count('signature:s:'), 1)
        self.assertEqual(signed.count('signscope:s:'), 1)
        self.assertNotIn('OLDBOGUS', signed)

    def test_sign_rdp_mirrors_full_address_to_alternate(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        rdp_text = 'full address:s:host.example.com\r\n'
        signed = rdp.sign_rdp(rdp_text, cert=cert, key=key, chain=[])
        self.assertIn('alternate full address:s:host.example.com', signed)
        signscope = next(l for l in signed.splitlines() if l.startswith('signscope:s:'))
        self.assertIn('Alternate Full Address', signscope)

    def test_sign_rdp_keeps_existing_alternate(self) -> None:
        cert, key = cf.self_signed('SIGNER', is_ca=False)
        rdp_text = (
            'full address:s:primary.example.com\r\n'
            'alternate full address:s:backup.example.com\r\n'
        )
        signed = rdp.sign_rdp(rdp_text, cert=cert, key=key, chain=[])
        self.assertIn('alternate full address:s:backup.example.com', signed)
        self.assertNotIn('alternate full address:s:primary.example.com', signed)

    # ------------------------------------------------------------------ _load_cert_key_chain
    def test_load_cert_key_chain_pem_pair(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, leaf_key = cf.issue('LEAF', inter_cert, inter_key)
        self.install_trust(root_cert)

        cert_path = self.write('cert.pem', cf.chain_to_pem(leaf_cert, inter_cert))
        key_path = self.write('key.pem', cf.key_to_pem(leaf_key))

        with override_settings(RDP_SIGN_CERT=str(cert_path), RDP_SIGN_KEY=str(key_path)):
            loaded_leaf, loaded_key, loaded_chain = rdp._load_cert_key_chain()

        self.assertEqual(loaded_leaf.subject, leaf_cert.subject)
        self.assertEqual(
            loaded_key.public_key().public_numbers(), leaf_key.public_key().public_numbers()
        )
        self.assertEqual([c.subject for c in loaded_chain], [inter_cert.subject])

    def test_load_cert_key_chain_pkcs12(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, leaf_key = cf.issue('LEAF', inter_cert, inter_key)
        self.install_trust(root_cert)

        pfx_bytes = pkcs12.serialize_key_and_certificates(
            name=b'leaf',
            key=leaf_key,
            cert=leaf_cert,
            cas=[inter_cert],
            encryption_algorithm=serialization.NoEncryption(),
        )
        pfx_path = self.write('bundle.pfx', pfx_bytes)

        with override_settings(RDP_SIGN_CERT=str(pfx_path), RDP_SIGN_KEY='/does/not/matter'):
            loaded_leaf, loaded_key, loaded_chain = rdp._load_cert_key_chain()

        self.assertEqual(loaded_leaf.subject, leaf_cert.subject)
        self.assertEqual(
            loaded_key.public_key().public_numbers(), leaf_key.public_key().public_numbers()
        )
        self.assertEqual([c.subject for c in loaded_chain], [inter_cert.subject])

    def test_load_cert_key_chain_empty_pem_raises(self) -> None:
        cert_path = self.write('empty.pem', b'')
        key_path = self.write('key.pem', cf.key_to_pem(cf.make_rsa_key()))
        with override_settings(RDP_SIGN_CERT=str(cert_path), RDP_SIGN_KEY=str(key_path)):
            with self.assertRaises(ValueError):
                rdp._load_cert_key_chain()

    def test_sign_rdp_settings_includes_chain_in_pkcs7(self) -> None:
        # Chain certs must be embedded in the PKCS7 SignedData so verifiers can build the path.
        from cryptography.hazmat.primitives.serialization import pkcs7 as _pkcs7
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, leaf_key = cf.issue('LEAF', inter_cert, inter_key)

        sig_b64, _ = rdp.sign_rdp_settings(
            ['full address:s:host'], cert=leaf_cert, key=leaf_key, chain=[inter_cert]
        )
        raw = base64.b64decode(sig_b64)
        # Strip 12-byte rdpsign header → DER PKCS7
        embedded = _pkcs7.load_der_pkcs7_certificates(raw[12:])
        subjects = {c.subject for c in embedded}
        self.assertIn(leaf_cert.subject, subjects)
        self.assertIn(inter_cert.subject, subjects)

    def test_sign_rdp_with_ec_key(self) -> None:
        # End-to-end with EC key (PKCS7 supports RSA + EC).
        ec_key = ec.generate_private_key(ec.SECP256R1())
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        from cryptography.x509.oid import NameOID
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc)
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'EC-SIGNER')])
        cert = (
            x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(ec_key.public_key())
            .serial_number(1)
            .not_valid_before(now - _dt.timedelta(days=1))
            .not_valid_after(now + _dt.timedelta(days=30))
            .sign(ec_key, hashes.SHA256())
        )
        signed = rdp.sign_rdp('full address:s:host\r\n', cert=cert, key=ec_key, chain=[])
        self.assertIn('signature:s:', signed)

    def test_load_cert_key_chain_key_mismatch_raises(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        leaf_cert, _ = cf.issue('LEAF', root_cert, root_key)
        self.install_trust(root_cert)

        wrong_key = cf.make_rsa_key()
        cert_path = self.write('cert.pem', cf.to_pem(leaf_cert))
        key_path = self.write('key.pem', cf.key_to_pem(wrong_key))

        with override_settings(RDP_SIGN_CERT=str(cert_path), RDP_SIGN_KEY=str(key_path)):
            with self.assertRaises(ValueError) as ctx:
                rdp._load_cert_key_chain()
        self.assertIn('does not match', str(ctx.exception))
