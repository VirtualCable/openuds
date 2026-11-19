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

import datetime

from uds import models
from uds.core.environment import Environment
from uds.core.types import log
from uds.core.util import config
from uds.core.util.model import sql_now
from uds.workers.log import LogMaintenance

from ...utils.test import UDSTestCase

MAX_ELEMENTS = 10
EXTRA_ELEMENTS = 5
OWNER_ID = 1


class LogMaintenanceTest(UDSTestCase):
    def setUp(self) -> None:
        previous_max = config.GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.get()
        self.addCleanup(config.GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.set, previous_max)
        config.GlobalConfig.INDIVIDIAL_LOG_MAX_ELEMENTS.set(str(MAX_ELEMENTS))
        log.LogObjectType.get_max_elements.cache_clear()
        self.addCleanup(log.LogObjectType.get_max_elements.cache_clear)

    def _create_logs(self, owner_type: log.LogObjectType, count: int) -> list[int]:
        start = sql_now() - datetime.timedelta(hours=1)
        return [
            models.Log.objects.create(
                owner_id=OWNER_ID,
                owner_type=owner_type.value,
                created=start + datetime.timedelta(seconds=i),
                data=f"entry {i}",
            ).pk
            for i in range(count)
        ]

    def _run_job(self) -> None:
        LogMaintenance(Environment.testing_environment()).run()

    def test_keeps_newest_entries_when_over_limit(self) -> None:
        ids = self._create_logs(log.LogObjectType.USERSERVICE, MAX_ELEMENTS + EXTRA_ELEMENTS)

        self._run_job()

        kept = list(
            models.Log.objects.filter(owner_id=OWNER_ID, owner_type=log.LogObjectType.USERSERVICE.value)
            .order_by("created", "id")
            .values_list("id", flat=True)
        )
        self.assertEqual(kept, ids[EXTRA_ELEMENTS:])

    def test_keeps_everything_when_under_limit(self) -> None:
        ids = self._create_logs(log.LogObjectType.USERSERVICE, MAX_ELEMENTS)

        self._run_job()

        kept = list(
            models.Log.objects.filter(owner_id=OWNER_ID, owner_type=log.LogObjectType.USERSERVICE.value)
            .order_by("created", "id")
            .values_list("id", flat=True)
        )
        self.assertEqual(kept, ids)
