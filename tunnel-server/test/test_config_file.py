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
import hashlib

from unittest import TestCase

from . import fixtures


class TestConfigFile(TestCase):
    def test_config_file(self) -> None:
        # Test in-memory configuration files ramdomly created
        for _ in range(100):
            values, cfg = fixtures.get_config()

            h = hashlib.sha256()
            h.update(values.get('secret', '').encode())
            secret = h.hexdigest()
            # Ensure data is correct
            self.assertEqual(cfg.pidfile, values['pidfile'])
            self.assertEqual(cfg.user, values['user'])
            self.assertEqual(cfg.log_level, values['loglevel'])
            self.assertEqual(cfg.log_file, values['logfile'])
            self.assertEqual(
                cfg.log_size, values['logsize'] * 1024 * 1024
            )  # Config file is in MB
            self.assertEqual(cfg.log_number, values['lognumber'])
            self.assertEqual(cfg.listen_address, values['address'])
            self.assertEqual(cfg.workers, values['workers'])
            self.assertEqual(cfg.ssl_certificate, values['ssl_certificate'])
            self.assertEqual(cfg.ssl_certificate_key, values['ssl_certificate_key'])
            self.assertEqual(cfg.ssl_ciphers, values['ssl_ciphers'])
            self.assertEqual(cfg.ssl_dhparam, values['ssl_dhparam'])
            self.assertEqual(cfg.uds_server, values['uds_server'])
            self.assertEqual(cfg.uds_token, values['uds_token'])
            self.assertEqual(cfg.uds_timeout, values['uds_timeout'])
            self.assertEqual(cfg.secret, secret)
            self.assertEqual(cfg.allow, {values['allow']})
            self.assertEqual(cfg.uds_verify_ssl, values['uds_verify_ssl'])
