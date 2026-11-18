#
# Copyright (c) 2024 Virtual Cable S.L.
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

import dataclasses
import unittest

from uds.services.Xen.xen import types as xen_types


def _failed_task(result: str = '', error_info: list[str] | None = None) -> xen_types.TaskInfo:
    task = xen_types.TaskInfo.unknown_task('OpaqueRef:task')
    return dataclasses.replace(
        task,
        name='VM.clone',
        status=xen_types.TaskStatus.FAILURE,
        result=result,
        error_info=error_info or [],
    )


class TestXenTaskInfoFailureReason(unittest.TestCase):
    def test_uses_error_info_when_present(self) -> None:
        task = _failed_task(error_info=['SR_FULL', 'OpaqueRef:sr'])

        self.assertEqual(task.failure_reason(), 'SR_FULL / OpaqueRef:sr')

    def test_error_info_wins_over_result(self) -> None:
        task = _failed_task(result='ignored', error_info=['SR_FULL'])

        self.assertEqual(task.failure_reason(), 'SR_FULL')

    def test_falls_back_to_result_without_error_info(self) -> None:
        task = _failed_task(result='ERROR, BOOM!')

        self.assertEqual(task.failure_reason(), 'ERROR, BOOM!')

    def test_names_the_task_when_nothing_else_is_known(self) -> None:
        task = _failed_task()

        self.assertEqual(task.failure_reason(), 'XAPI task VM.clone failed')
