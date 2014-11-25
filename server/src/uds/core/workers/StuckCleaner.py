# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from uds.models import DeployedService, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs.Job import Job
from uds.core.util import log
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

MAX_STUCK_TIME = 3600 * 24 * 2  # At most 2 days "Stuck", not configurable (there is no need to)


class StuckCleaner(Job):
    '''
    Kaputen Cleaner is very similar to Hanged Cleaner, at start, almost a copy
    We keep it in a new place to "control" more specific thins
    '''
    frecuency = 3600 * 24  # Executes Once a day
    friendly_name = 'Stuck States cleaner'

    def __init__(self, environment):
        super(StuckCleaner, self).__init__(environment)

    def run(self):
        since_state = getSqlDatetime() - timedelta(seconds=MAX_STUCK_TIME)
        # Filter for locating machine not ready
        for ds in DeployedService.objects.all():
            logger.debug('Searching for stuck states for {0}'.format(ds))
            # Info states are removed on UserServiceCleaner and VALID_STATES are ok, or if "hanged", checked on "HangedCleaner"
            for us in ds.userServices.filter(state_date__lt=since_state).exclude(state__in=State.INFO_STATES + State.VALID_STATES):
                logger.debug('Found stuck user service {0}'.format(us))
                log.doLog(ds, log.ERROR, 'User service {0} has been hard removed because it\'s stuck'.format(us.friendly_name))
                # us.delete()
