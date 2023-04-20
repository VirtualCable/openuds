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
import logging
import typing

from uds.core.util import singleton
from uds.models.notifications import Notification, LogLevel

if typing.TYPE_CHECKING:
    from ..messaging import provider

logger = logging.getLogger(__name__)


class NotificationsManager(metaclass=singleton.Singleton):
    """
    This class manages alerts and notifications
    """

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'NotificationsManager':
        return (
            NotificationsManager()
        )  # Singleton pattern will return always the same instance

    def notify(
        self,
        group: str,
        identificator: str,
        level: LogLevel,
        message: str,
        *args
    ) -> None:
        logger.debug(
            'Notify: %s, %s, %s, %s, [%s]', group, identificator, level, message, args
        )
        # Format the string
        try:
            message = message % args
        except Exception:
            message = message + ' ' + str(args) + ' (format error)'
        # Store the notification on local persistent storage
        # Will be processed by UDS backend
        with Notification.atomicPersistent():
            notify = Notification(
                group=group, identificator=identificator, level=level, message=message
            )
            Notification.savePersistent(notify)

    def registerGroup(self, group: str) -> None:
        """
        Registers a new group.
        This is used to group notifications
        """

    def registerIdentificator(self, group: str, identificator: str) -> None:
        """
        Registers a new identificator.
        This is used to identify notifications
        """
