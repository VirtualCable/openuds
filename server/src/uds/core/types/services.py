# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import dataclasses
import enum


class ServiceType(enum.StrEnum):
    VDI = 'VDI'
    VAPP = 'VAPP'

    def from_str(self, value: str) -> 'ServiceType':
        """Returns the service type from a string"""
        return ServiceType(value.upper())


class ServicesCountingType(enum.IntEnum):
    # 0 -> Standard max count type, that is, count only "creating and running" instances
    # 1 -> Count all instances, including "waint for delete" and "deleting" ones
    STANDARD = 0
    CONSERVATIVE = 1

    @staticmethod
    def from_int(value: int) -> 'ServicesCountingType':
        """Returns the MaxServiceCountingMethodType from an int
        If the int is not a valid value, returns STANDARD
        """
        try:
            return ServicesCountingType(value)
        except ValueError:
            return ServicesCountingType.STANDARD

    @staticmethod
    def from_str(value: str) -> 'ServicesCountingType':
        """Returns the MaxServiceCountingMethodType from an str
        If the str is not a valid value, returns STANDARD
        """
        try:
            return ServicesCountingType[value]
        except KeyError:
            return ServicesCountingType.STANDARD


@dataclasses.dataclass
class ConsoleConnectionTicket:
    value: str = ''
    expires: str = ''


@dataclasses.dataclass
class ConsoleConnectionInfo:
    type: str
    address: str
    port: int = -1
    secure_port: int = -1
    cert_subject: str = ''
    ticket: ConsoleConnectionTicket = dataclasses.field(default_factory=ConsoleConnectionTicket)

    ca: str = ''
    proxy: str = ''
    monitors: int = 0


@dataclasses.dataclass
class ConnectionData:
    host: str = ''
    username: str = ''
    password: str = ''


class ReadyStatus(enum.IntEnum):
    ZERO = 0x0000
    USERSERVICE_NOT_READY = 0x0001
    USERSERVICE_NO_IP = 0x0002
    TRANSPORT_NOT_READY = 0x0003
    USERSERVICE_INVALID_UUID = 0x0004

    def as_percent(self) -> int:
        """
        Returns the code as a percentage (0-100)
        """
        return 25 * self.value

    @staticmethod
    def from_int(value: int) -> 'ReadyStatus':
        try:
            return ReadyStatus(value)
        except ValueError:
            return ReadyStatus.USERSERVICE_NOT_READY

class CacheLevel(enum.IntEnum):
    NONE = 0  # : Constant for User cache level (no cache at all)
    L1 = 1  # : Constant for Cache of level 1
    L2 = 2  # : Constant for Cache of level 2


class Operation(enum.IntEnum):
    """
    Generic Operation type, to be used as a "status" for operations on userservices

    Notes:
      * We set all numbers to VERY HIGH, so we can use the same class for all services
      * Note that we will need to "translate" old values to new ones on the service,
      * Adapting existing services to this, will probably need a migration
    """
    # Standard operations 1000-1999
    INITIALIZE = 1000
    CREATE = 1001
    CREATE_COMPLETED = 1002
    START = 1003
    START_COMPLETED = 1004
    STOP = 1005  # This is a "hard" shutdown, like a power off
    STOP_COMPLETED = 1006
    SHUTDOWN = 1007  # This is a "soft" shutdown
    SHUTDOWN_COMPLETED = 1008
    SUSPEND = 1009  # If not provided, Suppend is a "soft" shutdown
    SUSPEND_COMPLETED = 1010
    RESET = 1011
    RESET_COMPLETED = 1012
    DELETE = 1013
    DELETE_COMPLETED = 1014
    
    WAIT = 1100  # This is a "wait" operation, used to wait for something to happen
    NOP = 1101
    RETRY = 1102  # Do not have executors, inserted to retry operation and recognize it
    
    # Custom validations 2000-2999
    DESTROY_VALIDATOR = 2000  # Check if the userservice has an vmid to stop destroying it if needed

    # Specific operations 3000-3999
    
    # for Fixed User Services
    SNAPSHOT_CREATE = 3000
    SNAPSHOT_RECOVER = 3001
    PROCESS_TOKEN = 3002

    # Final operations 9000-9999
    ERROR = 9000
    FINISH = 9900
    UNKNOWN = 9999

    # Some custom values, jut in case anyone needs them
    # For example, on a future, all fixed userservice will be moved
    # to this model, and we will need to "translate" the old values to the new ones
    # So we will translate, for example SNAPSHOT_CREATE to CUSTOM_1, etc..
    # Fixed user services does not allows custom operations, we use them
    # to alias some fixed operations (like snapshot create, recover, etc..)
    
    # Custom operations 20000-29999
    CUSTOM_1 = 20001
    CUSTOM_2 = 20002
    CUSTOM_3 = 20003
    CUSTOM_4 = 20004
    CUSTOM_5 = 20005
    CUSTOM_6 = 20006
    CUSTOM_7 = 20007
    CUSTOM_8 = 20008
    CUSTOM_9 = 20009
    
    def is_custom(self) -> bool:
        """
        Returns if the operation is a custom one
        """
        return self.value >= Operation.CUSTOM_1.value

    @staticmethod
    def from_int(value: int) -> 'Operation':
        try:
            return Operation(value)
        except ValueError:
            return Operation.UNKNOWN
        
    def as_str(self) -> str:
        return self.name

