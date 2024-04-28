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
import logging
import typing

from django.apps import apps
from django.db import connections

from uds.core import types
from uds.core.util import singleton

if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class NotificationsManager(metaclass=singleton.Singleton):
    """
    This class manages alerts and notifications
    """

    _initialized: bool = False

    def _ensure_local_db_exists(self) -> bool:
        if not apps.ready:
            return False
        if self._initialized:
            return True
        # Ensure notifications table exists on local sqlite db (called "persistent" on settings.py)
        # Note: On Notification model change, we must ensure that the table is removed on the migration itself
        from uds.models.notifications import Notification  # pylint: disable=import-outside-toplevel

        try:
            with connections['persistent'].schema_editor() as schema_editor:
                schema_editor.create_model(Notification)
        except Exception:  # nosec: intentionally catching all exceptions
            # If it fails, it's ok, it just means that it already exists
            pass
        self._initialized = True
        return True

    @staticmethod
    def manager() -> 'NotificationsManager':
        return NotificationsManager()  # Singleton pattern will return always the same instance

    def notify(self, group: str, identificator: str, level: types.log.LogLevel, message: str, *args: typing.Any) -> None:
        from uds.models.notifications import Notification  # pylint: disable=import-outside-toplevel

        # Due to use of local db, we must ensure that it exists (and cannot do it on ready)
        if self._ensure_local_db_exists() is False:
            return  # Not initialized apps yet, so we cannot do anything

        # logger.debug(
        #    'Notify: %s, %s, %s, %s, [%s]', group, identificator, level, message, args
        # )
        # Format the string
        try:
            message = message % args
        except Exception:
            message = message + ' ' + str(args) + ' (format error)'
        message = message[:4096]  # Max length of message
        # Store the notification on local persistent storage
        # Will be processed by UDS backend
        try:
            with Notification.atomic_persistent():
                notify = Notification(group=group, identificator=identificator, level=level, message=message)
                notify.save_persistent()
        except Exception:
            logger.info('Error saving notification %s, %s, %s, %s', group, identificator, level, message)
