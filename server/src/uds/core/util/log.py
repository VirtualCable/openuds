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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from uds.core.managers import logManager

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)
useLogger = logging.getLogger('useLog')

# Logging levels
OTHER, DEBUG, INFO, WARNING, ERROR, CRITICAL = (
    10000 * (x + 1) for x in range(6)
)  # @UndefinedVariable

WARN = WARNING
FATAL  = CRITICAL

# Logging sources
INTERNAL, ACTOR, TRANSPORT, OSMANAGER, UNKNOWN, WEB, ADMIN, SERVICE, REST = (
    'internal',
    'actor',
    'transport',
    'osmanager',
    'unknown',
    'web',
    'admin',
    'service',
    'rest',
)

OTHERSTR, DEBUGSTR, INFOSTR, WARNSTR, ERRORSTR, FATALSTR = (
    'OTHER',
    'DEBUG',
    'INFO',
    'WARN',
    'ERROR',
    'FATAL',
)

# Names for defined log levels
__nameLevels = {
    DEBUGSTR: DEBUG,
    INFOSTR: INFO,
    WARNSTR: WARN,
    ERRORSTR: ERROR,
    FATALSTR: FATAL,
    OTHERSTR: OTHER,
}

# Reverse dict of names
__valueLevels = {v: k for k, v in __nameLevels.items()}

# Global log owner types:
OWNER_TYPE_GLOBAL = -1
OWNER_TYPE_REST = -2


def logLevelFromStr(level: str) -> int:
    """
    Gets the numeric log level from an string.
    """
    return __nameLevels.get(level.upper(), OTHER)


def logStrFromLevel(level: int) -> str:
    return __valueLevels.get(level, 'OTHER')


def useLog(
    type_: str,
    serviceUniqueId: str,
    serviceIp: str,
    username: str,
    srcIP: typing.Optional[str] = None,
    srcUser: typing.Optional[str] = None,
    userServiceName: typing.Optional[str] = None,
    poolName: typing.Optional[str] = None,
) -> None:
    """
    Logs an "use service" event (logged from actors)
    :param type_: Type of event (commonly 'login' or 'logout')
    :param serviceUniqueId: Unique id of service
    :param serviceIp: IP Of the service
    :param username: Username notified from service (internal "user service" user name
    :param srcIP: IP of user holding that service at time of event
    :param srcUser: Username holding that service at time of event
    """
    srcIP = 'unknown' if srcIP is None else srcIP
    srcUser = 'unknown' if srcUser is None else srcUser
    userServiceName = 'unknown' if userServiceName is None else userServiceName
    poolName = 'unknown' if poolName is None else poolName

    useLogger.info(
        '|'.join(
            [
                type_,
                serviceUniqueId,
                serviceIp,
                srcIP,
                srcUser,
                username,
                userServiceName,
                poolName,
            ]
        )
    )


def doLog(
    wichObject: 'Model',
    level: int,
    message: str,
    source: str = UNKNOWN,
    avoidDuplicates: bool = True,
) -> None:
    logger.debug('%s %s %s', wichObject, level, message)
    logManager().doLog(wichObject, level, message, source, avoidDuplicates)


def getLogs(
    wichObject: 'Model', limit: typing.Optional[int] = None
) -> typing.List[typing.Dict]:
    """
    Get the logs associated with "wichObject", limiting to "limit" (default is GlobalConfig.MAX_LOGS_PER_ELEMENT)
    """
    from uds.core.util.config import GlobalConfig

    if limit is None:
        limit = GlobalConfig.MAX_LOGS_PER_ELEMENT.getInt()

    return logManager().getLogs(wichObject, limit)


def clearLogs(wichObject: 'Model') -> None:
    """
    Clears the logs associated with the object using the logManager
    """
    return logManager().clearLogs(wichObject)
