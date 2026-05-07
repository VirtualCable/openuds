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

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from django.test import override_settings

from uds.core.managers.crypto import certs

from . import _cert_factory as cf


class CertsTest(cf.CertTestCase):
    # ------------------------------------------------------------------ paths
    @override_settings(RDP_SIGN_CERT='/custom/cert.pem', RDP_SIGN_KEY='/custom/key.pem')
    def test_get_server_cert_override(self) -> None:
        self.assertEqual(certs.get_server_cert(), '/custom/cert.pem')
        self.assertEqual(certs.get_server_key(), '/custom/key.pem')

    # ------------------------------------------------------------------ loaders
    def test_load_certificates_all_formats(self) -> None:
        root, _ = cf.self_signed('ROOT')
        leaf, _ = cf.self_signed('LEAF', is_ca=False)

        cases: list[tuple[str, bytes, set[object]]] = [
            ('PEM chain', cf.chain_to_pem(leaf, root), {leaf.subject, root.subject}),
            ('DER single', cf.to_der(leaf), {leaf.subject}),
            ('PKCS7 PEM', pkcs7.serialize_certificates([leaf, root], serialization.Encoding.PEM), {leaf.subject, root.subject}),
            ('PKCS7 DER', pkcs7.serialize_certificates([leaf, root], serialization.Encoding.DER), {leaf.subject, root.subject}),
        ]
        for label, blob, expected in cases:
            with self.subTest(format=label):
                loaded = certs.load_certificates_any_format(blob)
                self.assertEqual({c.subject for c in loaded}, expected)

    def test_load_certificates_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            certs.load_certificates_any_format(b'not a cert')

    def test_load_private_key_pem_and_der(self) -> None:
        _, key = cf.self_signed('K')
        for label, blob in (('PEM', cf.key_to_pem(key)), ('DER', cf.key_to_der(key))):
            with self.subTest(format=label):
                loaded = certs.load_private_key_any_format(blob)
                self.assertEqual(
                    loaded.public_key().public_numbers(), key.public_key().public_numbers()
                )

    def test_load_private_key_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            certs.load_private_key_any_format(b'not a key')

    def test_load_pem_certificates_reads_file(self) -> None:
        cert, _ = cf.self_signed('FILE')
        path = self.write('c.pem', cf.to_pem(cert))
        for label, arg in (('str', str(path)), ('Path', path)):
            with self.subTest(arg_type=label):
                loaded = certs.load_pem_certificates(arg)
                self.assertEqual(loaded[0].subject, cert.subject)

    # ------------------------------------------------------------------ system roots
    def test_load_system_roots_uses_override(self) -> None:
        root, _ = cf.self_signed('OVERRIDE-ROOT')
        bundle = self.write('ca.pem', cf.to_pem(root))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(bundle)):
            loaded = certs.load_system_roots()
        self.assertEqual([c.subject for c in loaded], [root.subject])

    def test_load_system_roots_caches_result(self) -> None:
        root, _ = cf.self_signed('CACHED-ROOT')
        bundle = self.write('ca.pem', cf.to_pem(root))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(bundle)):
            first = certs.load_system_roots()
            bundle.unlink()
            second = certs.load_system_roots()
        self.assertIs(first, second)

    def test_load_system_roots_missing_bundle_returns_empty(self) -> None:
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'does-not-exist.pem')):
            loaded = certs.load_system_roots()
        self.assertEqual(loaded, [])

    # ------------------------------------------------------------------ chain validation
    def test_check_cert_chain_self_signed_leaf(self) -> None:
        leaf_cert, _ = cf.self_signed('selfsigned-leaf', is_ca=False)
        path = self.write('leaf.pem', cf.to_pem(leaf_cert))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            certs.check_cert_chain(path)  # no raise

    def test_check_cert_chain_valid_with_intermediate(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        self.install_trust(root_cert)
        path = self.write('chain.pem', cf.chain_to_pem(leaf_cert, inter_cert))
        certs.check_cert_chain(path)

    def test_check_cert_chain_root_bundled_anchors(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            path = self.write('full.pem', cf.chain_to_pem(leaf_cert, inter_cert, root_cert))
            certs.check_cert_chain(path)

    def test_check_cert_chain_incomplete_raises(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            path = self.write('leaf-only.pem', cf.to_pem(leaf_cert))
            with self.assertRaises(ValueError) as ctx:
                certs.check_cert_chain(path)
        self.assertIn('Incomplete chain', str(ctx.exception))

    def test_check_cert_chain_expired_raises(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        expired_cert, _ = cf.self_signed(
            'EXPIRED',
            not_before=now - datetime.timedelta(days=30),
            not_after=now - datetime.timedelta(days=1),
        )
        path = self.write('exp.pem', cf.to_pem(expired_cert))
        with self.assertRaises(ValueError) as ctx:
            certs.check_cert_chain(path)
        self.assertIn('expired or not yet valid', str(ctx.exception))

    def test_check_cert_chain_empty_file_raises(self) -> None:
        path = self.write('empty.pem', b'')
        with self.assertRaises(ValueError):
            certs.check_cert_chain(path)

    def test_check_chain_in_memory_ok(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        self.install_trust(root_cert)
        certs.check_chain(leaf_cert, [inter_cert])

    def test_check_chain_in_memory_incomplete_raises(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            with self.assertRaises(ValueError):
                certs.check_chain(leaf_cert, [])

    def test_check_chain_not_yet_valid_raises(self) -> None:
        now = datetime.datetime.now(datetime.timezone.utc)
        future_cert, _ = cf.self_signed(
            'FUTURE',
            not_before=now + datetime.timedelta(days=1),
            not_after=now + datetime.timedelta(days=365),
        )
        path = self.write('fut.pem', cf.to_pem(future_cert))
        with self.assertRaises(ValueError) as ctx:
            certs.check_cert_chain(path)
        self.assertIn('expired or not yet valid', str(ctx.exception))

    def test_check_chain_broken_signature_raises(self) -> None:
        # intermediate names ROOT as issuer but was signed by some other key
        root_cert, _ = cf.self_signed('ROOT')
        rogue_key = cf.make_rsa_key()
        inter_cert, inter_key = cf.issue('INTER', root_cert, rogue_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        self.install_trust(root_cert)
        with self.assertRaises(ValueError) as ctx:
            certs.check_chain(leaf_cert, [inter_cert])
        self.assertIn('signature invalid', str(ctx.exception))

    def test_check_chain_depth_exceeded_raises(self) -> None:
        # chain longer than _MAX_CHAIN_DEPTH with no anchor in trust
        root_cert, root_key = cf.self_signed('R')
        prev_cert, prev_key = root_cert, root_key
        intermediates: list[x509.Certificate] = []
        for i in range(certs._MAX_CHAIN_DEPTH + 2):
            c, k = cf.issue(f'I{i}', prev_cert, prev_key, is_ca=True)
            intermediates.append(c)
            prev_cert, prev_key = c, k
        leaf, _ = cf.issue('LEAF', prev_cert, prev_key)
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            with self.assertRaises(ValueError) as ctx:
                certs.check_chain(leaf, intermediates)
        self.assertIn('Chain depth exceeded', str(ctx.exception))
