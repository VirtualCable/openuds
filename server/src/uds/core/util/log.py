# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import os
import logging
import logging.handlers
import typing
import re

from django.apps import apps

from uds.core.types.log import LogLevel, LogSource

try:
    from systemd import journal
except ImportError:
    journal = None

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

use_logger = logging.getLogger('useLog')


# Pattern for look for date and time in this format: 2023-04-20 04:03:08,776 (and trailing spaces)
# This is the format used by python logging module
DATETIME_PATTERN: typing.Final[typing.Pattern[str]] = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) *')
# Pattern for removing the LOGLEVEL from the log line beginning
LOGLEVEL_PATTERN: typing.Final[typing.Pattern[str]] = re.compile(r'^(DEBUG|INFO|WARNING|ERROR|CRITICAL) *')



def log_use(
    type_: str,
    service_unique_id: str,
    service_ip: str,
    username: str,
    src_ip: typing.Optional[str] = None,
    src_user: typing.Optional[str] = None,
    userservice_name: typing.Optional[str] = None,
    servicepool_name: typing.Optional[str] = None,
) -> None:
    """
    Logs an "use service" event (logged from actors)
    
    Args:
        type_: Type of event (login, logout, etc)
        service_unique_id: Unique id of the service
        service_ip: IP of the service
        username: Username of the user
        src_ip: IP of the source (if any)
        src_user: Username of the source (if any)
        userservice_name: Name of the userservice (if any)
        servicepool_name: Name of the servicepool (if any)
        
    """
    src_ip = 'unknown' if src_ip is None else src_ip
    src_user = 'unknown' if src_user is None else src_user
    userservice_name = 'unknown' if userservice_name is None else userservice_name
    servicepool_name = 'unknown' if servicepool_name is None else servicepool_name

    use_logger.info(
        '|'.join(
            [
                type_,
                service_unique_id,
                service_ip,
                src_ip,
                src_user,
                username,
                userservice_name,
                servicepool_name,
            ]
        )
    )

    # Will be stored on database by UDSLogHandler


def log(
    db_object: typing.Optional['Model'],
    level: LogLevel,
    message: str,
    source: LogSource = LogSource.UNKNOWN,
    log_name: typing.Optional[str] = None,
) -> None:
    # pylint: disable=import-outside-toplevel
    from uds.core.managers.log import LogManager

    LogManager.manager().log(db_object, level, message, source, log_name)


def get_logs(wichObject: typing.Optional['Model'], limit: int = -1) -> list[dict[str, typing.Any]]:
    """
    Get the logs associated with "wichObject", limiting to "limit" (default is GlobalConfig.MAX_LOGS_PER_ELEMENT)
    """
    # pylint: disable=import-outside-toplevel
    from uds.core.managers.log import LogManager

    return LogManager().get_logs(wichObject, limit)


def clear_logs(wichObject: typing.Optional['Model']) -> None:
    """
    Clears the logs associated with the object using the logManager
    """
    # pylint: disable=import-outside-toplevel
    from uds.core.managers.log import LogManager

    LogManager().clear_logs(wichObject)


class UDSLogHandler(logging.handlers.RotatingFileHandler):
    """
    Custom log handler that will log to database before calling to RotatingFileHandler
    """

    # Protects from recursive calls
    emiting: typing.ClassVar[bool] = False

    def emit(self, record: logging.LogRecord) -> None:
        # To avoid circular imports and loading manager before apps are ready
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.notifications import NotificationsManager

        def _format_msg(*, clear_level: bool) -> str:
            msg = self.format(record)
            # Remove date and time from message, as it will be stored on database
            msg = DATETIME_PATTERN.sub('', msg)
            if clear_level:
                # Remove log level from message, as it will be stored on database
                msg = LOGLEVEL_PATTERN.sub('', msg)
            return msg

        def notify(msg: str, identificator: str, loglevel: LogLevel) -> None:
            NotificationsManager.manager().notify('log', identificator, loglevel, msg)

        if apps.ready and record.levelno >= logging.INFO and not UDSLogHandler.emiting:
            try:
                # Convert to own loglevel, basically multiplying by 1000
                log_level = LogLevel.from_logging_level(record.levelno)
                UDSLogHandler.emiting = True
                identificator = os.path.basename(self.baseFilename)
                msg = _format_msg(clear_level=True)
                if record.levelno >= logging.WARNING:
                    # Remove traceback from message, as it will be stored on database
                    notify(msg.splitlines()[0], identificator, log_level)
                log(None, log_level, msg, LogSource.LOGS, identificator)
            except Exception:  # nosec: If cannot log, just ignore it
                pass
            finally:
                UDSLogHandler.emiting = False

        # Send warning and error messages to systemd journal
        if record.levelno >= logging.WARNING:
            msg = _format_msg(clear_level=False)
            # Send to systemd journaling, transforming identificator and priority
            identificator = 'UDS-' + os.path.basename(self.baseFilename).split('.')[0]
            # convert syslog level to systemd priority
            # Systemd priority levels are:
            #  "emerg" (0), "alert" (1), "crit" (2), "err" (3),
            #  "warning" (4), "notice" (5), "info" (6), "debug" (7)
            # Log levels are:
            # "CRITICAL" (50), "ERROR" (40), "WARNING" (30), "INFO" (20), "DEBUG" (10), "NOTSET" (0)
            # Note, priority will be always 4 (WARNING), 3(ERROR), or 2(CRITICAL)
            priority = 4 if record.levelno == logging.WARNING else 3 if record.levelno == logging.ERROR else 2

            if journal is not None:
                journal.send(MESSAGE=msg, PRIORITY=priority, SYSLOG_IDENTIFIER=identificator)  # pyright: ignore[reportUnknownMemberType]

        return super().emit(record)
