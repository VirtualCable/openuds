# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import logging
from datetime import timedelta

from django.db.models import Q, Count

from uds.core.jobs import Job
from uds.core.util.config import GlobalConfig
from uds.core.util.state import State
from uds.models import ServicePool
from uds.core.util.model import sql_datetime

logger = logging.getLogger(__name__)


class AssignedAndUnused(Job):
    frecuency = 300  # Once every 5 minute, but look for GlobalConfig.CHECK_UNUSED_TIME
    frecuency_cfg = GlobalConfig.CHECK_UNUSED_DELAY
    friendly_name = 'Unused services checker'

    def run(self) -> None:
        since_state = sql_datetime() - timedelta(
            seconds=GlobalConfig.CHECK_UNUSED_TIME.getInt()
        )
        # Locate service pools with pending assigned service in use
        outdatedServicePools = ServicePool.objects.annotate(
            outdated=Count(
                'userServices',
                filter=Q(
                    userServices__in_use=False,
                    userServices__state_date__lt=since_state,
                    userServices__state=State.USABLE,
                    userServices__os_state=State.USABLE,
                    userServices__cache_level=0,
                ),
            )
        ).filter(outdated__gt=0, state=State.ACTIVE)
        for ds in outdatedServicePools:
            # Skips checking deployed services in maintenance mode or ignores assigned and unused
            if ds.isInMaintenance() or ds.ignores_unused:
                continue
            unusedMachines = ds.assignedUserServices().filter(
                in_use=False,
                state_date__lt=since_state,
                state=State.USABLE,
                os_state=State.USABLE,
            )
            # If do not needs os manager, this is
            if ds.osmanager:
                osm = ds.osmanager.get_instance()
                if osm.processUnusedMachines:
                    logger.debug(
                        'Processing unused services for %s, %s', ds, ds.osmanager
                    )
                    for us in unusedMachines:
                        logger.debug('Found unused assigned service %s', us)
                        osm.processUnused(us)
            else:  # No os manager, simply remove unused services in specified time
                for us in unusedMachines:
                    logger.debug(
                        'Found unused assigned service with no OS Manager %s', us
                    )
                    us.release()
