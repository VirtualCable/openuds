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
from datetime import datetime, timedelta
import logging
import typing

from django.db.models import Q, Count

from uds.models import ServicePool, UserService
from uds.core.util.model import getSqlDatetime
from uds.core.util.state import State
from uds.core.jobs import Job
from uds.core.util import log

logger = logging.getLogger(__name__)

MAX_STUCK_TIME = (
    3600 * 24
)  # At most 1 days "Stuck", not configurable (there is no need to)


class StuckCleaner(Job):
    """
    Kaputen Cleaner is very similar to Hanged Cleaner
    We keep it in a new place to "control" more specific thins
    """

    frecuency = 3601 * 8  # Executes every 8 hours
    friendly_name = 'Stuck States cleaner'

    def run(self) -> None:
        since_state: datetime = getSqlDatetime() - timedelta(seconds=MAX_STUCK_TIME)
        # Filter for locating machine stuck on removing, cancelling, etc..
        # Locate service pools with pending assigned service in use
        servicePoolswithStucks = (
            ServicePool.objects.annotate(
                stuckCount=Count(
                    'userServices',
                    filter=Q(userServices__state_date__lt=since_state)
                    & (
                        Q(
                            userServices__state=State.PREPARING,
                            userServices__properties__name='destroy_after',
                        )
                        | ~Q(
                            userServices__state__in=State.INFO_STATES
                            + State.VALID_STATES
                        )
                    ),
                )
            )
            .filter(service__provider__maintenance_mode=False, state=State.ACTIVE)
            .exclude(stuckCount=0)
        )

        # Info states are removed on UserServiceCleaner and VALID_STATES are ok, or if "hanged", checked on "HangedCleaner"
        def stuckUserServices(servicePool: ServicePool) -> typing.Iterable[UserService]:
            q = servicePool.userServices.filter(state_date__lt=since_state)
            # Get all that are not in valid or info states, AND the ones that are "PREPARING" with
            # "destroy_after" property set (exists) (that means that are waiting to be destroyed after initializations)
            yield from q.exclude(state__in=State.INFO_STATES + State.VALID_STATES)
            yield from q.filter(state=State.PREPARING, properties__name='destroy_after')

        for servicePool in servicePoolswithStucks:
            # logger.debug('Searching for stuck states for %s', servicePool.name)
            for stuck in stuckUserServices(servicePool):
                logger.debug('Found stuck user service %s', stuck)
                log.doLog(
                    servicePool,
                    log.LogLevel.ERROR,
                    f'User service {stuck.name} has been hard removed because it\'s stuck',
                )
                # stuck.setState(State.ERROR)
                stuck.delete()
