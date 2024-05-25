# -*- coding: utf-8 -*-
#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import logging
import typing

from uds import reports

from tests.utils.test import UDSTestCase


logger = logging.getLogger(__name__)

# UUid of the reports
# Here we only want to ensure the code has no errors, so we only check that they load correctly
MUST_HAVE: typing.Final[list[str]] = [
    'a5a43bc0-d543-11ea-af8f-af01fa65994e',
    '5da93a76-1849-11e5-ac1a-10feed05884b',
    '8cd1cfa6-ed48-11e4-83e5-10feed05884b',
    'b5f5ebc8-44e9-11ed-97a9-efa619da6a49',
    '765b5580-1840-11e5-8137-10feed05884b',
    '0f62f19a-f166-11e4-8f59-10feed05884b',
    '6445b526-24ce-11e5-b3cb-10feed05884b',
    '88932b48-1fd3-11e5-a776-10feed05884b',
    '1491148a-2fc6-11e7-a5ad-03d9a417561c',
    '0b429f70-2fc6-11e7-9a2a-8fc37101e66a',
    '5f7f0844-beb1-11e5-9a96-10feed05884b',
    '811b1261-82c4-524e-b1c7-a4b7fe70050f',
    'aba55fe5-c4df-5240-bbe6-36340220cb5d',
    '38ec12dc-beaf-11e5-bd0a-10feed05884b',
    '302e1e76-30a8-11e7-9d1e-6762bbf028ca',
    '202c6438-30a8-11e7-80e4-77c1e4cb9e09',
]


class TestReports(UDSTestCase):
    """
    Test known transports are registered correctly
    """

    def test_reports_loads_correctly(self) -> None:
        # Reports loaded at top level

        for i in reports.available_reports:
            self.assertIn(i.uuid, MUST_HAVE)
