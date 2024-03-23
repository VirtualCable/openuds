# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# We use commit/rollback
from ...utils.test import UDSTransactionTestCase
from uds.core.util.cache import Cache
import time

# Some random chars, that include unicode non-ascci chars
UNICODE_CHARS = 'ñöçóá^(pípè)'
UNICODE_CHARS_2 = 'ñöçóá^(€íöè)'
VALUE_1 = [u'únîcödè€', b'string', {'a': 1, 'b': 2.0}]


class CacheTest(UDSTransactionTestCase):
    def test_cache(self) -> None:
        cache = Cache(UNICODE_CHARS)

        # Get default value, with unicode
        self.assertEqual(
            cache.get(UNICODE_CHARS, UNICODE_CHARS_2),
            UNICODE_CHARS_2,
            'Unicode unexisting key returns default unicode',
        )

        # Remove unexisting key, not a problem
        self.assertEqual(cache.remove('non-existing-1'), False, 'Removing unexisting key')

        # Add new key (non existing) with default duration (60 seconds probable)
        cache.put(UNICODE_CHARS_2, VALUE_1)

        # checks it
        self.assertEqual(cache.get(UNICODE_CHARS_2), VALUE_1, 'Put a key and recover it')

        # Add new "str" key, with 1 second life, wait 2 seconds and recover
        cache.put(b'key', VALUE_1, 1)
        time.sleep(1.1)
        self.assertEqual(
            cache.get(b'key'),
            None,
            'Put an "str" key and recover it once it has expired',
        )

        # Refresh previous key and will be again available
        cache.refresh(b'key')
        self.assertEqual(
            cache.get(b'key'),
            VALUE_1,
            'Refreshed cache key is {} and should be {}'.format(cache.get(b'key'), VALUE_1),
        )

        # Checks cache clean
        cache.put('key', VALUE_1)
        cache.clear()
        self.assertEqual(cache.get('key'), None, 'Get key from cleaned cache')

        # Checks cache purge
        cache.put('key', 'test')
        Cache.purge()
        self.assertEqual(cache.get('key'), None, 'Get key from purged cache')

        # Checks cache cleanup (remove expired keys)
        cache.put('key', 'test', 0)
        time.sleep(0.1)
        Cache.purge_outdated()
        cache.refresh('key')
        self.assertEqual(
            cache.get('key'),
            None,
            'Put a key and recover it once it has expired and has been cleaned',
        )

