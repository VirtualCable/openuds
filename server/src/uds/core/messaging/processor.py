# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import time
import logging
import typing

from uds.core.managers.task import BaseThread

from uds.models import Notifier, Notification
from uds.core.util.model import getSqlDatetime
from .provider import Notifier as NotificationProviderModule, LogLevel
from .config import DO_NOT_REPEAT

logger = logging.getLogger(__name__)

WAIT_TIME = 8  # seconds
CACHE_TIMEOUT = 64  # seconds


class MessageProcessorThread(BaseThread):
    keepRunning: bool = True

    _cached_providers: typing.Optional[
        typing.List[typing.Tuple[int, NotificationProviderModule]]
    ]
    _cached_stamp: float

    def __init__(self):
        super().__init__()
        self.name = 'MessageProcessorThread'
        self._cached_providers = None
        self._cached_stamp = 0.0

    @property
    def providers(self) -> typing.List[typing.Tuple[int, NotificationProviderModule]]:
        # If _cached_providers is invalid or _cached_time is older than CACHE_TIMEOUT,
        # we need to refresh it
        if (
            self._cached_providers is None
            or time.time() - self._cached_stamp > CACHE_TIMEOUT
        ):
            self._cached_providers = [
                (p.level, p.getInstance()) for p in Notifier.objects.all()
            ]
            self._cached_stamp = time.time()
        return self._cached_providers

    def run(self):
        while self.keepRunning:
            # Locate all notifications from "persistent" and try to process them
            # If no notification can be fully resolved, it will be kept in the database
            for n in Notification.getPersistentQuerySet().all():
                # If there are any other notification simmilar to this on default db, skip it
                # Simmilar means that group and identificator are present and it has less than DO_NOT_REPEAT seconds
                # from last time
                if Notification.objects.filter(
                    group=n.group,
                    identificator=n.identificator,
                    stamp__gt=getSqlDatetime()
                    - datetime.timedelta(seconds=DO_NOT_REPEAT.getInt()),
                ).exists():
                    # Remove it from the persistent db
                    n.deletePersistent()
                    continue
                # Try to insert into Main DB
                notify = (
                    not n.processed
                )  # If it was already processed, the only thing left is to add to maind DB and remove it from persistent
                pk = n.pk
                n.processed = True
                try:
                    n.pk = None
                    n.save(using='default')
                    # Delete from Persistent DB, first restore PK
                    n.pk = pk
                    n.deletePersistent()
                    logger.debug('Saved notification %s to main DB', n)
                except Exception:
                    # try notificators, but keep on db with error
                    # Restore pk, and save locally so we can try again
                    n.pk = pk
                    try:
                        Notification.savePersistent(n)
                    except Exception:
                        logger.error('Error saving notification %s to persistent DB', n)
                        continue
                    # Process notificators, but this is kept on db with processed flat as True
                    # logger.warning(
                    #     'Could not save notification %s to main DB, trying notificators',
                    #    n,
                    #)

                if notify:
                    for p in (i[1] for i in self.providers if i[0] >= n.level):
                        # if we are asked to stop, we don't try to send anymore
                        if not self.keepRunning:
                            break
                        p.notify(
                            n.group,
                            n.identificator,
                            LogLevel.fromInt(n.level),
                            n.message,
                        )

            for _ in range(WAIT_TIME):
                if not self.keepRunning:
                    break
                time.sleep(1)

    def notifyTermination(self):
        self.keepRunning = False
