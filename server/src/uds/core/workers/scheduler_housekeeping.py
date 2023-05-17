# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from datetime import timedelta
import time
import logging

from django.db import transaction

from uds.models import Scheduler
from uds.core.util.model import getSqlDatetime
from uds.core.util.state import State
from uds.core.jobs import Job

logger = logging.getLogger(__name__)

MAX_EXECUTION_MINUTES = 15  # Minutes


class SchedulerHousekeeping(Job):
    """
    Ensures no task is executed for more than 15 minutes
    """

    frecuency = 301  # Frecuncy for this job
    friendly_name = 'Scheduler house keeping'

    def run(self) -> None:
        """
        Look for "hanged" scheduler tasks and reschedule them
        """
        since = getSqlDatetime() - timedelta(minutes=MAX_EXECUTION_MINUTES)
        for _ in range(3):  # Retry three times in case of lockout error
            try:
                with transaction.atomic():
                    Scheduler.objects.select_for_update(skip_locked=True).filter(
                        last_execution__lt=since, state=State.RUNNING
                    ).update(owner_server='', state=State.FOR_EXECUTE)
                break
            except Exception:
                logger.info('Retrying Scheduler cleanup transaction')
                time.sleep(1)
