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
import logging
import typing

from django.db import transaction
from uds.core import managers
from uds.core.util.config import GlobalConfig
from uds.models import UserService, getSqlDatetime
from uds.core.util.state import State
from uds.core.jobs import Job

logger = logging.getLogger(__name__)

# Notas:
# Clean cache info items. DONE
# Initiate removal of "removable" cached items, with a limit (at most X per run). DONE
# Look for non current cache items and mark them as removables.


class UserServiceInfoItemsCleaner(Job):
    frecuency = 14401
    frecuency_cfg = (
        GlobalConfig.KEEP_INFO_TIME
    )  # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'User Service Info Cleaner'

    def run(self) -> None:
        removeFrom = getSqlDatetime() - timedelta(
            seconds=GlobalConfig.KEEP_INFO_TIME.getInt(True)
        )
        logger.debug('Removing information user services from %s', removeFrom)
        with transaction.atomic():
            UserService.objects.select_for_update().filter(
                state__in=State.INFO_STATES, state_date__lt=removeFrom
            ).delete()


class UserServiceRemover(Job):
    frecuency = 31
    frecuency_cfg = (
        GlobalConfig.REMOVAL_CHECK
    )  # Request run cache "info" cleaner every configued seconds. If config value is changed, it will be used at next reload
    friendly_name = 'User Service Cleaner'

    def run(self) -> None:
        # USER_SERVICE_REMOVAL_LIMIT is the maximum number of items to remove at once
        # This configuration value is cached at startup, so it is not updated until next reload
        removeAtOnce: int = GlobalConfig.USER_SERVICE_CLEAN_NUMBER.getInt()
        manager = managers.userServiceManager()

        with transaction.atomic():
            removeFrom = getSqlDatetime() - timedelta(
                seconds=10
            )  # We keep at least 10 seconds the machine before removing it, so we avoid connections errors
            removableUserServices: typing.Iterable[
                UserService
            ] = UserService.objects.filter(
                state=State.REMOVABLE,
                state_date__lt=removeFrom,
                deployed_service__service__provider__maintenance_mode=False,
            ).iterator(
                chunk_size=removeAtOnce
            )

        # We remove at once, but we limit the number of items to remove

        for removableUserService in removableUserServices:
            # if removal limit is reached, we stop
            if removeAtOnce <= 0:
                break
            logger.debug('Checking removal of %s', removableUserService.name)
            try:
                if manager.canRemoveServiceFromDeployedService(
                    removableUserService.deployed_service
                ):
                    manager.remove(removableUserService)
                    removeAtOnce -= 1  # We promoted one removal
            except Exception:
                logger.exception('Exception removing user service')
