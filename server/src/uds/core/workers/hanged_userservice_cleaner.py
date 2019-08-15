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
from datetime import timedelta
import logging

from django.db.models import Q
from uds.core.util.Config import GlobalConfig
from uds.models import ServicePool, getSqlDatetime
from uds.core.util.State import State
from uds.core.jobs import Job
from uds.core.util import log

logger = logging.getLogger(__name__)


class HangedCleaner(Job):
    frecuency = 3601
    frecuency_cfg = GlobalConfig.MAX_INITIALIZING_TIME
    friendly_name = 'Hanged services checker'

    def run(self):
        since_state = getSqlDatetime() - timedelta(seconds=GlobalConfig.MAX_INITIALIZING_TIME.getInt())
        # Filter for locating machine not ready
        flt = Q(state_date__lt=since_state, state=State.PREPARING) | Q(state_date__lt=since_state, state=State.USABLE, os_state=State.PREPARING) | Q(state_date__lt=since_state, state=State.REMOVING)

        # Type
        servicePool: ServicePool

        for servicePool in ServicePool.objects.exclude(osmanager=None, state__in=State.VALID_STATES, service__provider__maintenance_mode=True):
            logger.debug('Searching for hanged services for %s', servicePool)
            for us in servicePool.userServices.filter(flt):
                logger.debug('Found hanged service %s', us)
                log.doLog(us, log.ERROR, 'User Service seems to be hanged. Removing it.', log.INTERNAL)
                log.doLog(servicePool, log.ERROR, 'Removing user service {0} because it seems to be hanged'.format(us.friendly_name))
                if us.state in (State.REMOVING,):
                    us.setState(State.ERROR)
                else:
                    us.removeOrCancel()
