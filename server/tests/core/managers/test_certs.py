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
import pathlib
import tempfile
import typing

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs7

from django.test import override_settings

from uds.core.managers.crypto import certs

from ...utils.test import UDSTestCase
from . import _cert_factory as cf


class CertsTest(UDSTestCase):
    _tmpdir: tempfile.TemporaryDirectory[str]
    tmp: pathlib.Path

    def setUp(self) -> None:
        super().setUp()
        # Reset module-level system trust cache so each test can inject its own bundle
        certs._system_trust_cache = None  # type: ignore[attr-defined]
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = pathlib.Path(self._tmpdir.name)

    def tearDown(self) -> None:
        certs._system_trust_cache = None  # type: ignore[attr-defined]
        self._tmpdir.cleanup()
        super().tearDown()

    def _write(self, name: str, data: bytes) -> pathlib.Path:
        p = self.tmp / name
        p.write_bytes(data)
        return p

    # ------------------------------------------------------------------ paths
    def test_get_server_cert_default(self) -> None:
        # No setting set -> default path
        self.assertEqual(certs.get_server_cert(), '/etc/certs/server.pem')
        self.assertEqual(certs.get_server_key(), '/etc/certs/key.pem')

    @override_settings(RDP_SIGN_CERT='/custom/cert.pem', RDP_SIGN_KEY='/custom/key.pem')
    def test_get_server_cert_override(self) -> None:
        self.assertEqual(certs.get_server_cert(), '/custom/cert.pem')
        self.assertEqual(certs.get_server_key(), '/custom/key.pem')

    # ------------------------------------------------------------------ loaders
    def test_load_certificates_pem(self) -> None:
        root_cert, _ = cf.self_signed('ROOT')
        leaf_cert, _ = cf.self_signed('LEAF', is_ca=False)
        loaded = certs.load_certificates_any_format(cf.chain_to_pem(leaf_cert, root_cert))
        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0].subject, leaf_cert.subject)
        self.assertEqual(loaded[1].subject, root_cert.subject)

    def test_load_certificates_der(self) -> None:
        cert, _ = cf.self_signed('DER-CERT')
        loaded = certs.load_certificates_any_format(cf.to_der(cert))
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].subject, cert.subject)

    def test_load_certificates_pkcs7_pem(self) -> None:
        root, _ = cf.self_signed('ROOT')
        leaf, _ = cf.self_signed('LEAF', is_ca=False)
        blob = pkcs7.serialize_certificates([leaf, root], serialization.Encoding.PEM)
        loaded = certs.load_certificates_any_format(blob)
        self.assertEqual({c.subject for c in loaded}, {leaf.subject, root.subject})

    def test_load_certificates_pkcs7_der(self) -> None:
        root, _ = cf.self_signed('ROOT')
        leaf, _ = cf.self_signed('LEAF', is_ca=False)
        blob = pkcs7.serialize_certificates([leaf, root], serialization.Encoding.DER)
        loaded = certs.load_certificates_any_format(blob)
        self.assertEqual({c.subject for c in loaded}, {leaf.subject, root.subject})

    def test_load_certificates_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            certs.load_certificates_any_format(b'not a cert')

    def test_load_private_key_pem(self) -> None:
        _, key = cf.self_signed('K')
        loaded = certs.load_private_key_any_format(cf.key_to_pem(key))
        self.assertEqual(
            loaded.public_key().public_numbers(),
            key.public_key().public_numbers(),
        )

    def test_load_private_key_der(self) -> None:
        _, key = cf.self_signed('K')
        loaded = certs.load_private_key_any_format(cf.key_to_der(key))
        self.assertEqual(
            loaded.public_key().public_numbers(),
            key.public_key().public_numbers(),
        )

    def test_load_private_key_invalid_raises(self) -> None:
        with self.assertRaises(ValueError):
            certs.load_private_key_any_format(b'not a key')

    def test_load_pem_certificates_reads_file(self) -> None:
        cert, _ = cf.self_signed('FILE')
        path = self._write('c.pem', cf.to_pem(cert))
        # Accepts both str and Path
        loaded_from_str = certs.load_pem_certificates(str(path))
        loaded_from_path = certs.load_pem_certificates(path)
        self.assertEqual(loaded_from_str[0].subject, cert.subject)
        self.assertEqual(loaded_from_path[0].subject, cert.subject)

    # ------------------------------------------------------------------ system roots
    def test_load_system_roots_uses_override(self) -> None:
        root, _ = cf.self_signed('OVERRIDE-ROOT')
        bundle = self._write('ca.pem', cf.to_pem(root))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(bundle)):
            loaded = certs.load_system_roots()
        self.assertEqual([c.subject for c in loaded], [root.subject])

    def test_load_system_roots_caches_result(self) -> None:
        root, _ = cf.self_signed('CACHED-ROOT')
        bundle = self._write('ca.pem', cf.to_pem(root))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(bundle)):
            first = certs.load_system_roots()
            # Remove the file; cached copy must still be returned
            bundle.unlink()
            second = certs.load_system_roots()
        self.assertIs(first, second)

    def test_load_system_roots_missing_bundle_returns_empty(self) -> None:
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'does-not-exist.pem')):
            loaded = certs.load_system_roots()
        self.assertEqual(loaded, [])

    # ------------------------------------------------------------------ chain validation
    def _install_trust(self, *roots: typing.Any) -> None:
        bundle = self._write('trust.pem', cf.chain_to_pem(*roots))
        self._trust_override = override_settings(RDP_SIGN_CA_BUNDLE=str(bundle))
        self._trust_override.enable()
        self.addCleanup(self._trust_override.disable)

    def test_check_cert_chain_self_signed_leaf(self) -> None:
        # self-signed leaf, no trust bundle: passes (but logs a warning)
        leaf_cert, _ = cf.self_signed('selfsigned-leaf', is_ca=False)
        path = self._write('leaf.pem', cf.to_pem(leaf_cert))
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            certs.check_cert_chain(path)  # no raise

    def test_check_cert_chain_valid_with_intermediate(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        self._install_trust(root_cert)
        path = self._write('chain.pem', cf.chain_to_pem(leaf_cert, inter_cert))
        certs.check_cert_chain(path)  # no raise

    def test_check_cert_chain_root_bundled_anchors(self) -> None:
        # Leaf + intermediate + root all in the chain file; trust store empty.
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            path = self._write('full.pem', cf.chain_to_pem(leaf_cert, inter_cert, root_cert))
            certs.check_cert_chain(path)

    def test_check_cert_chain_incomplete_raises(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        # Trust store doesn't know the root AND chain file is missing intermediate
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            path = self._write('leaf-only.pem', cf.to_pem(leaf_cert))
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
        path = self._write('exp.pem', cf.to_pem(expired_cert))
        with self.assertRaises(ValueError) as ctx:
            certs.check_cert_chain(path)
        self.assertIn('expired or not yet valid', str(ctx.exception))

    def test_check_cert_chain_empty_file_raises(self) -> None:
        path = self._write('empty.pem', b'')
        with self.assertRaises(ValueError):
            certs.check_cert_chain(path)

    def test_check_chain_in_memory_ok(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        self._install_trust(root_cert)
        certs.check_chain(leaf_cert, [inter_cert])  # no raise

    def test_check_chain_in_memory_incomplete_raises(self) -> None:
        root_cert, root_key = cf.self_signed('ROOT')
        inter_cert, inter_key = cf.issue('INTER', root_cert, root_key, is_ca=True)
        leaf_cert, _ = cf.issue('LEAF', inter_cert, inter_key)
        # No trust and no intermediate bundled
        with override_settings(RDP_SIGN_CA_BUNDLE=str(self.tmp / 'missing.pem')):
            with self.assertRaises(ValueError):
                certs.check_chain(leaf_cert, [])
