# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import dataclasses
import enum

from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model


logger = logging.getLogger(__name__)

@dataclasses.dataclass
class _ObjTypeInfo:
    obj_type: int
    model: 'type[Model]'
    
@enum.unique
class ObjectType(enum.Enum):
    PROVIDER = _ObjTypeInfo(1, models.Provider)
    SERVICE = _ObjTypeInfo(2, models.Service)
    OSMANAGER = _ObjTypeInfo(3, models.OSManager)
    TRANSPORT = _ObjTypeInfo(4, models.Transport)
    NETWORK = _ObjTypeInfo(5, models.Network)
    POOL = _ObjTypeInfo(6, models.ServicePool)
    USER_SERVICE = _ObjTypeInfo(7, models.UserService)
    AUTHENTICATOR = _ObjTypeInfo(8, models.Authenticator)
    USER = _ObjTypeInfo(9, models.User)
    GROUP = _ObjTypeInfo(10, models.Group)
    STATS_COUNTER = _ObjTypeInfo(11, models.StatsCounters)
    STATS_EVENTS = _ObjTypeInfo(12, models.StatsEvents)
    CALENDAR = _ObjTypeInfo(13, models.Calendar)
    CALENDAR_RULE = _ObjTypeInfo(14, models.CalendarRule)
    METAPOOL = _ObjTypeInfo(15, models.MetaPool)
    ACCOUNT = _ObjTypeInfo(16, models.Account)
    # Actor and Tunnel tokens are now on REGISTERED_SERVER, so removed
    MFA = _ObjTypeInfo(19, models.MFA)
    REGISTERED_SERVER = _ObjTypeInfo(20, models.Server)
    REGISTERED_SERVER_GROUP = _ObjTypeInfo(21, models.ServerGroup)
    ACCOUNT_USAGE = _ObjTypeInfo(22, models.AccountUsage)
    IMAGE = _ObjTypeInfo(23, models.Image)
    LOG = _ObjTypeInfo(24, models.Log)
    NOTIFICATION = _ObjTypeInfo(25, models.Notification)
    TICKET_STORE = _ObjTypeInfo(26, models.TicketStore)

    @property
    def model(self) -> type['Model']:
        return self.value.model

    @property
    def type(self) -> int:
        """Returns the integer value of this object type. (The "type" id)"""
        return self.value.obj_type

    @staticmethod
    def from_model(model: 'Model') -> 'ObjectType':
        for objType in ObjectType:
            if objType.model == type(model):
                return objType
        raise ValueError(f'Invalid model type: {model}')

    def __eq__(self, __o: object) -> bool:
        """Compares with another ObjType, and includes int comparison

        Args:
            __o (object): Object to compare

        Returns:
            bool: True if equal, False otherwise
            
        Examples:
            >>> ObjectType.PROVIDER == ObjectType.PROVIDER
            True
            >>> ObjectType.PROVIDER == 1
            True
            >>> ObjectType.PROVIDER == ObjectType.SERVICE
            False
            >>> ObjectType.PROVIDER == 2
            False
        """
        return super().__eq__(__o) or self.value.obj_type == __o
