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
# pyright: reportUnusedImport=false
import enum
import time
import typing
from datetime import datetime

from . import actor, auth, cache, calendar, images, net, os, system, ticket, rest, services, transports, ui

# Date related constants
NEVER: typing.Final[datetime] = datetime(1972, 7, 1)
NEVER_UNIX: typing.Final[int] = int(time.mktime(NEVER.timetuple()))

# Unknown mac address "magic" value
MAC_UNKNOWN: typing.Final[str] = '00:00:00:00:00:00'

# REST Related constants
OK: typing.Final[str] = 'ok'  # Constant to be returned when result is just "operation complete successfully"

# For conversion to boolean
BOOL_TRUE_VALUES: typing.Final[typing.Set[typing.Union[bool, str, bytes, int]]] = {
    True,
    'TRUE',
    'True',
    b'true',
    b'True',
    b'TRUE',
    1,
    '1',
    b'1',
    'true',
    'YES',
    'Yes',
    'yes',
    'ENABLED',
    'Enabled',
    'enabled',
}
TRUE_STR: typing.Final[str] = 'true'
FALSE_STR: typing.Final[str] = 'false'

# Constant to mark an "UNLIMITED" value
UNLIMITED: typing.Final[int] = -1

# Constant marking no more names available
NO_MORE_NAMES: typing.Final[str] = 'NO-NAME-ERROR'


class UserRole(enum.StrEnum):
    """
    Roles for users
    """

    ADMIN = 'admin'
    STAFF = 'staff'

    # Currently not used, but reserved
    USER = 'user'
    ANONYMOUS = 'anonymous'
    
    @property
    def needs_authentication(self) -> bool:
        """
        Checks if this role needs authentication
        
        Returns:
            True if this role needs authentication, False otherwise
        """
        return self != UserRole.ANONYMOUS

    def can_access(self, role: 'UserRole') -> bool:
        """
        Checks if this role can access to the requested role
        
        That is, if this role is greater or equal to the requested role
        
        Args:
            role: Role to check against
            
        Returns:
            True if this role can access to the requested role, False otherwise
        """
        ROLE_PRECEDENCE: typing.Final = {
            UserRole.ADMIN: 3,
            UserRole.STAFF: 2,
            UserRole.USER: 1,
            UserRole.ANONYMOUS: 0,
        }

        return ROLE_PRECEDENCE[self] >= ROLE_PRECEDENCE[role]
