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
Author: Andres Schumann, aschumann at virtualcable dot es
"""

import uuid

from uds.core import environment
from uds.core.services.generics.dynamic.service import DynamicService
from uds.core.util import fields

from ....utils.test import UDSTestCase
from . import fixtures


class PutBackToCacheTestingService(fixtures.DynamicTestingService):
    put_back_to_cache = fields.put_back_to_cache_field()


def create_service() -> DynamicService:
    service_uuid = str(uuid.uuid4())
    return PutBackToCacheTestingService(
        provider=fixtures.create_dynamic_provider(),
        environment=environment.Environment.private_environment(service_uuid),
        uuid=service_uuid,
    )


class DynamicPutBackToCacheTest(UDSTestCase):
    def test_unset_value_does_not_allow_putting_back_to_cache(self) -> None:
        service = create_service()
        self.assertFalse(service.allow_putting_back_to_cache())

    def test_no_does_not_allow_putting_back_to_cache(self) -> None:
        service = create_service()
        service.put_back_to_cache.value = "no"
        self.assertFalse(service.allow_putting_back_to_cache())

    def test_yes_allows_putting_back_to_cache(self) -> None:
        service = create_service()
        service.put_back_to_cache.value = "yes"
        self.assertTrue(service.allow_putting_back_to_cache())

    def test_snapshot_allows_putting_back_to_cache(self) -> None:
        service = create_service()
        service.put_back_to_cache.value = "snapshot"
        self.assertTrue(service.allow_putting_back_to_cache())
