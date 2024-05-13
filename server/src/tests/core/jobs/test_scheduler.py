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
import time
import threading
from tracemalloc import stop
import typing
from unittest import mock

from django.test import TransactionTestCase

from uds.core.jobs import scheduler, jobs_factory


class SchedulerTest(TransactionTestCase):
    def setUp(self) -> None:
        scheduler.Scheduler.granularity = 0.1  # type: ignore  # Speed up tests

    def test_init_execute_and_shutdown(self) -> None:
        sch = scheduler.Scheduler()
        # Patch:
        # * execute_job to call notify_termination
        # * release_own_shedules to do nothing
        # * jobs_factory.JobsFactory().ensure_jobs_registered to do nothing (JobsFactory is a singleton)
        with mock.patch.object(sch, 'execute_job') as mock_execute_job, mock.patch.object(
            sch, 'release_own_schedules'
        ) as mock_release_own_schedules, mock.patch.object(
            jobs_factory.JobsFactory(), 'ensure_jobs_registered'
        ) as mock_ensure_jobs_registered:
            left = 4

            def _our_execute_job(*args: typing.Any, **kwargs: typing.Any) -> None:
                nonlocal left
                left -= 1
                if left == 0:
                    sch.notify_termination()

            mock_execute_job.side_effect = _our_execute_job

            # Execute run, but if it does not call execute_job, it will hang
            # so we execute a thread that will call notify_termination after 1 second
            stop_event = threading.Event()

            def _ensure_stops() -> None:
                stop_event.wait(scheduler.Scheduler.granularity * 10)
                if left > 0:
                    sch.notify_termination()

            watchdog = threading.Thread(target=_ensure_stops)
            watchdog.start()

            sch.run()

            # If watchdog is alive, it means that notify_termination was not called
            if watchdog.is_alive():
                stop_event.set()
                watchdog.join()

            self.assertEqual(left, 0)  # If left is 0, it means that execute_job was called 4 times
            mock_release_own_schedules.assert_called_once()
            mock_ensure_jobs_registered.assert_called_once()
