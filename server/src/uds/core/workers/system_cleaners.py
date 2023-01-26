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
from importlib import import_module
import logging
import datetime
import typing

from django.conf import settings
from uds.core.util.cache import Cache
from uds.core.jobs import Job
from uds.models import TicketStore, Log, getSqlDatetime
from uds.core.util import config, log

logger = logging.getLogger(__name__)


class CacheCleaner(Job):

    frecuency = 3600 * 24  # Once a day
    friendly_name = 'Utility Cache Cleaner'

    def run(self):
        logger.debug('Starting cache cleanup')
        Cache.cleanUp()
        logger.debug('Done cache cleanup')


class TicketStoreCleaner(Job):

    frecuency = 60  # every minute (60 seconds)
    friendly_name = 'Ticket Storage Cleaner'

    def run(self):
        logger.debug('Starting ticket storage cleanup')
        TicketStore.cleanup()
        logger.debug('Done ticket storage cleanup')


class SessionsCleaner(Job):
    frecuency = 3600 * 24 * 7  # Once a week will be enough
    friendly_name = 'User Sessions cleaner'

    def run(self):
        logger.debug('Starting session cleanup')
        try:
            engine: typing.Any = import_module(settings.SESSION_ENGINE)
        except Exception:
            logger.exception('DjangoSessionsCleaner')
            return

        try:
            engine.SessionStore.clear_expired()
        except NotImplementedError:
            pass  # No problem if no cleanup

        logger.debug('Done session cleanup')


class AuditLogCleanup(Job):
    frecuency = 60 * 60 * 24  # Once a day
    friendly_name = 'Audit Log Cleanup'

    def run(self) -> None:
        """
        Cleans logs older than days
        """
        Log.objects.filter(
            created__lt=getSqlDatetime()
            - datetime.timedelta(
                days=config.GlobalConfig.MAX_AUDIT_LOGS_DURATION.getInt()
            ),
            owner_type=log.OWNER_TYPE_AUDIT,
        ).delete()
