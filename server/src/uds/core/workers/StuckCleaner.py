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
from datetime import datetime, timedelta
import logging
import typing

from uds.models import ServicePool, UserService, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs import Job
from uds.core.util import log

logger = logging.getLogger(__name__)

MAX_STUCK_TIME = 3600 * 24 * 2  # At most 2 days "Stuck", not configurable (there is no need to)


class StuckCleaner(Job):
    """
    Kaputen Cleaner is very similar to Hanged Cleaner, at start, almost a copy
    We keep it in a new place to "control" more specific thins
    """
    frecuency = 3600 * 24  # Executes Once a day
    friendly_name = 'Stuck States cleaner'

    def run(self):
        since_state: datetime  = getSqlDatetime() - timedelta(seconds=MAX_STUCK_TIME)
        # Filter for locating machine not ready
        servicePoolsActive: typing.Iterable[ServicePool] = ServicePool.objects.filter(service__provider__maintenance_mode=False).iterator()
        for servicePool in servicePoolsActive:
            logger.debug('Searching for stuck states for %s', servicePool.name)
            stuckUserServices: typing.Iterable[UserService] = servicePool.userServices.filter(
                state_date__lt=since_state
            ).exclude(
                state__in=State.INFO_STATES + State.VALID_STATES
            ).iterator()
            # Info states are removed on UserServiceCleaner and VALID_STATES are ok, or if "hanged", checked on "HangedCleaner"
            for stuck in stuckUserServices:
                logger.debug('Found stuck user service %s', stuck)
                log.doLog(servicePool, log.ERROR, 'User service %s has been hard removed because it\'s stuck', stuck.name)
                stuck.delete()
