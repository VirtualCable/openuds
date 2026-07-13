# -*- coding: utf-8 -*-

#
# Copyright (c) 2026 Virtual Cable S.L.U.
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
from uds.core.util.auth import normalize_username


def test_normalize_username() -> None:
    # Idempotent
    clean = 'alice@example.com'
    assert normalize_username(clean) == clean
    assert normalize_username(normalize_username(clean)) == clean

    # BOM U+FEFF
    assert normalize_username('﻿alice@example.com') == clean
    assert normalize_username('alice﻿@example.com') == clean

    # Zero-width / format chars
    assert normalize_username('a\u200blice@example.com') == clean
    assert normalize_username('\u200calice\u200d@example.com') == clean
    assert normalize_username('alice\u00ad@example.com') == clean  # soft hyphen

    # NFKC: fullwidth -> ASCII
    assert normalize_username('\uff41\uff4c\uff49\uff43\uff45') == 'alice'

    # Control / NUL
    assert normalize_username('bob\x00-x') == 'bob-x'
    assert normalize_username('\tbob-x\n') == 'bob-x'

    # Case preserved
    assert normalize_username('Carol.Smith@Example.COM') == 'Carol.Smith@Example.COM'

    # Empty / falsy pass through
    assert normalize_username('') == ''
    assert normalize_username(None) is None  # type: ignore[arg-type]
