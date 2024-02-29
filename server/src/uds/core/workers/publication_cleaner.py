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
from datetime import timedelta
import logging
import collections.abc

from uds.core.managers import publication_manager
from uds.core.util.config import GlobalConfig
from uds.models import ServicePoolPublication
from uds.core.util.model import sql_datetime
from uds.core.services.exceptions import PublishException
from uds.core.types.states import State
from uds.core.jobs import Job

logger = logging.getLogger(__name__)


class PublicationInfoItemsCleaner(Job):
    frecuency = 3607
    frecuency_cfg = (
        GlobalConfig.CLEANUP_CHECK
    )  # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Publications Info Cleaner'

    def run(self) -> None:
        removeFrom = sql_datetime() - timedelta(
            seconds=GlobalConfig.KEEP_INFO_TIME.as_int(True)
        )
        ServicePoolPublication.objects.filter(
            state__in=State.INFO_STATES, state_date__lt=removeFrom
        ).delete()


class PublicationCleaner(Job):
    frecuency = 31
    frecuency_cfg = (
        GlobalConfig.REMOVAL_CHECK
    )  # Request run publication "removal" every configued seconds. If config value is changed, it will be used at next reload
    friendly_name = 'Publication Cleaner'

    def run(self) -> None:
        removables: collections.abc.Iterable[
            ServicePoolPublication
        ] = ServicePoolPublication.objects.filter(
            state=State.REMOVABLE,
            deployed_service__service__provider__maintenance_mode=False,
        )
        for removable in removables:
            try:
                publication_manager().unpublish(removable)
            except PublishException:  # Can say that it cant be removed right now
                logger.debug('Delaying removal')
