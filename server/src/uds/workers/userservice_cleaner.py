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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from datetime import timedelta
import logging
import typing
import collections.abc

from django.db import transaction
from uds.core.managers.userservice import UserServiceManager
from uds.core.util.config import GlobalConfig
from uds.models import UserService
from uds.core.util.model import sql_now
from uds.core.types.states import State
from uds.core.jobs import Job

logger = logging.getLogger(__name__)

# Notas:
# Clean cache info items. DONE
# Initiate removal of "removable" cached items, with a limit (at most X per run). DONE
# Look for non current cache items and mark them as removables.


class UserServiceInfoItemsCleaner(Job):
    frecuency = 600  # Constant time, every hour will check for old info items
    # frecuency_cfg = (
    #     GlobalConfig.KEEP_INFO_TIME
    # )  # Request run cache "info" cleaner every configured seconds. If config value is changed, it will be used at next reload
    friendly_name = 'User Service Info Cleaner'

    def run(self) -> None:
        remove_since = sql_now() - timedelta(seconds=GlobalConfig.KEEP_INFO_TIME.as_int(True))
        logger.debug('Removing information user services from %s', remove_since)
        with transaction.atomic():
            UserService.objects.select_for_update().filter(
                state__in=State.INFO_STATES, state_date__lt=remove_since
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
        max_to_remove: int = GlobalConfig.USER_SERVICE_CLEAN_NUMBER.as_int()
        manager = UserServiceManager.manager()

        with transaction.atomic():
            remove_since = sql_now() - timedelta(
                seconds=10
            )  # We keep at least 10 seconds the machine before removing it, so we avoid connections errors
            candidates: collections.abc.Iterable[UserService] = UserService.objects.filter(
                state=State.REMOVABLE,
                state_date__lt=remove_since,
                deployed_service__service__provider__maintenance_mode=False,
            ).iterator(chunk_size=max_to_remove)

        # We remove at once, but we limit the number of items to remove
        # Cache deployed_services that cannot remove to avoid checking them again
        not_removable_deployed_services: typing.Set[int] = set()

        for candidate in candidates:
            # if removal limit is reached, we stop
            if max_to_remove <= 0:
                break
            logger.debug('Checking removal of %s', candidate.name)
            try:
                if (
                    candidate.service_pool.id not in not_removable_deployed_services
                    and manager.is_userservice_removal_allowed(candidate.service_pool)
                ):
                    manager.remove(candidate)
                    max_to_remove -= 1  # We promoted one removal
                else:
                    not_removable_deployed_services.add(candidate.service_pool.id)
            except Exception:
                logger.exception('Exception removing user service')
