# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
from datetime import timedelta

from uds.core.jobs import Job
from uds.core.util.config import GlobalConfig
from uds.core.util.state import State
from uds.models import ServicePool, getSqlDatetime

logger = logging.getLogger(__name__)


class AssignedAndUnused(Job):
    frecuency = 61  # Once every minute, but look for GlobalConfig.CHECK_UNUSED_TIME since
    # frecuency_cfg = GlobalConfig.CHECK_UNUSED_TIME
    friendly_name = 'Unused services checker'

    def run(self):
        since_state = getSqlDatetime() - timedelta(seconds=GlobalConfig.CHECK_UNUSED_TIME)
        for ds in ServicePool.objects.all():
            # Skips checking deployed services in maintenance mode or ignores assigned and unused
            if ds.isInMaintenance() is True or ds.ignores_unused:
                continue
            # If do not needs os manager, this is
            if ds.osmanager is not None:
                osm = ds.osmanager.getInstance()
                if osm.processUnusedMachines is True:
                    logger.debug('Processing unused services for %s, %s', ds, ds.osmanager)
                    for us in ds.assignedUserServices().filter(in_use=False, state_date__lt=since_state, state=State.USABLE, os_state=State.USABLE):
                        logger.debug('Found unused assigned service %s', us)
                        osm.processUnused(us)
            else:  # No os manager, simply remove unused services in specified time
                for us in ds.assignedUserServices().filter(in_use=False, state_date__lt=since_state, state=State.USABLE, os_state=State.USABLE):
                    logger.debug('Found unused assigned service with no OS Manager %s', us)
                    us.remove()
