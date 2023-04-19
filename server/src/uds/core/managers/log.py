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
import traceback
import logging
import enum
import typing

from uds import models

from uds.core.util.config import GlobalConfig
from uds.core.util import singleton

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model


logger = logging.getLogger(__name__)


class LogObjectType(enum.IntEnum):
    USERSERVICE = 0
    PUBLICATION = 1
    SERVICEPOOL = 2
    SERVICE = 3
    PROVIDER = 4
    USER = 5
    GROUP = 6
    AUTHENTICATOR = 7
    METAPOOL = 8
    SYSLOG = 9

    def get_max_elements(self) -> int:
        """
        if True, this type of log will be limited by number of log entries
        """
        if self == LogObjectType.SYSLOG:
            return GlobalConfig.SYSLOG_MAX_ELEMENTS.getInt()
        return GlobalConfig.MAX_LOGS_PER_ELEMENT.getInt()


# Dict for translations
MODEL_TO_TYPE: typing.Mapping[typing.Type['Model'], LogObjectType] = {
    models.UserService: LogObjectType.USERSERVICE,
    models.ServicePoolPublication: LogObjectType.PUBLICATION,
    models.ServicePool: LogObjectType.SERVICEPOOL,
    models.Service: LogObjectType.SERVICE,
    models.Provider: LogObjectType.PROVIDER,
    models.User: LogObjectType.USER,
    models.Group: LogObjectType.GROUP,
    models.Authenticator: LogObjectType.AUTHENTICATOR,
    models.MetaPool: LogObjectType.METAPOOL,
}


class LogManager(metaclass=singleton.Singleton):
    """
    Manager for logging (at database) events
    """

    def __init__(self):
        pass

    @staticmethod
    def manager() -> 'LogManager':
        return LogManager()  # Singleton pattern will return always the same instance

    def __log(
        self,
        owner_type: LogObjectType,
        owner_id: int,
        level: int,
        message: str,
        source: str,
        avoidDuplicates: bool,
    ):
        """
        Logs a message associated to owner
        """
        # Ensure message fits on space
        message = str(message)[:255]

        qs = models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type.value)
        # First, ensure we do not have more than requested logs, and we can put one more log item
        max_elements = owner_type.get_max_elements()
        current_elements = qs.count()
        # If max_elements is greater than 0, database contains equals or more than max_elements, we will delete the oldest ones to ensure we have max_elements - 1
        if 0 < max_elements <= current_elements:
            # We will delete the oldest ones
            for x in qs.order_by('created', 'id')[:current_elements - max_elements + 1]:
                x.delete()

        if avoidDuplicates:
            lg: typing.Optional[models.Log] = models.Log.objects.filter(
                owner_id=owner_id, owner_type=owner_type.value
            ).last()
            if lg and lg.data == message:
                # Do not log again, already logged
                return

        # now, we add new log
        try:
            models.Log.objects.create(
                owner_type=owner_type.value,
                owner_id=owner_id,
                created=models.getSqlDatetime(),
                source=source,
                level=level,
                data=message,
            )
        except Exception:  # nosec
            # Some objects will not get logged, such as System administrator objects, but this is fine
            pass

    def __getLogs(
        self, owner_type: LogObjectType, owner_id: int, limit: int
    ) -> typing.List[typing.Dict]:
        """
        Get all logs associated with an user service, ordered by date
        """
        qs = models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type.value)
        return [
            {'date': x.created, 'level': x.level, 'source': x.source, 'message': x.data}
            for x in reversed(qs.order_by('-created', '-id')[:limit])  # type: ignore  # Slicing is not supported by pylance right now
        ]

    def __clearLogs(self, owner_type: LogObjectType, owner_id: int):
        """
        Clears ALL logs related to user service
        """
        models.Log.objects.filter(owner_id=owner_id, owner_type=owner_type).delete()

    def doLog(
        self,
        wichObject: typing.Optional['Model'],
        level: int,
        message: str,
        source: str,
        avoidDuplicates: bool = True,
    ):
        """
        Do the logging for the requested object.

        If the object provided do not accepts associated loggin, it simply ignores the request
        """
        owner_type = (
            MODEL_TO_TYPE.get(type(wichObject), None)
            if wichObject
            else LogObjectType.SYSLOG
        )
        objectId = getattr(wichObject, 'id', -1)

        if owner_type is not None:
            try:
                self.__log(
                    owner_type, objectId, level, message, source, avoidDuplicates
                )
            except Exception:
                logger.error(
                    'Error logging: %s:%s %s - %s %s',
                    owner_type,
                    objectId,
                    level,
                    message,
                    source,
                )
        else:
            logger.debug(
                'Requested doLog for a type of object not covered: %s', wichObject
            )

    def getLogs(
        self, wichObject: typing.Optional['Model'], limit: int
    ) -> typing.List[typing.Dict]:
        """
        Get the logs associated with "wichObject", limiting to "limit" (default is GlobalConfig.MAX_LOGS_PER_ELEMENT)
        """

        owner_type = (
            MODEL_TO_TYPE.get(type(wichObject), None)
            if wichObject
            else LogObjectType.SYSLOG
        )
        logger.debug('Getting log: %s -> %s', wichObject, owner_type)

        if owner_type:  # 0 is valid owner type
            return self.__getLogs(owner_type, getattr(wichObject, 'id', -1), limit)

        logger.debug(
            'Requested getLogs for a type of object not covered: %s', wichObject
        )
        return []

    def clearLogs(self, wichObject: typing.Optional['Model']):
        """
        Clears all logs related to wichObject

        Used mainly at object database removal (parent object)
        """

        owner_type = (
            MODEL_TO_TYPE.get(type(wichObject), None)
            if wichObject
            else LogObjectType.SYSLOG
        )
        if owner_type:
            self.__clearLogs(owner_type, getattr(wichObject, 'id', -1))
        else:
            logger.debug(
                'Requested clearLogs for a type of object not covered: %s: %s',
                type(wichObject),
                wichObject,
            )
            for line in traceback.format_stack(limit=5):
                logger.debug('>> %s', line)
