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
import typing

from .services import ServiceType


# For requests to actors/servers
class PreconnectRequest(typing.NamedTuple):
    """Information sent on a preconnect request"""

    udsuser: str  # UDS user name
    udsuser_uuid: str  # UDS user uuid
    service_type: ServiceType  # VDI or VAPP (as in ServiceType)
    userservice_uuid: str  # UUID of userservice

    user: str  # user that will login
    protocol: str  # protocol to use, (RDP, SPICE, etc..)
    ip: str  # IP of the client
    hostname: str  # Hostname of the client

    def asDict(self) -> typing.Dict[str, str]:
        return self._asdict()


# For requests to actors/servers
class AssignRequest(typing.NamedTuple):
    """Information sent on a assign request"""

    udsuser: str
    udsuser_uuid: str
    service_type: ServiceType  # VDI or VAPP (as in ServiceType)
    userservice_uuid: str  # UUID of userservice

    assignations: int  # Number of times this service has been assigned

    def asDict(self) -> typing.Dict[str, 'str|int']:
        return self._asdict()


class ConnectionData(typing.NamedTuple):
    """
    Connection data provided by transports, and contains all the "transformable" information needed to connect to a service
    (such as username, password, domain, etc..)
    """

    protocol: str  # protocol to use, (there are a few standard defined in 'protocols.py', if yours does not fit those, use your own name
    username: str  # username (transformed if needed to) used to login to service
    service_type: ServiceType  # If VDI or APP, Defaults to VDI
    password: str = ''  # password (transformed if needed to) used to login to service
    domain: str = (
        ''  # domain (extracted from username or wherever) that will be used. (Not necesarily an AD domain)
    )
    host: str = ''  # Used only for some transports that needs the host to connect to (like SPICE, RDS, etc..)

    # sso: bool = False  # For future sso implementation

    def asDict(self) -> typing.Dict[str, str]:
        return self._asdict()


class ConnectionSource(typing.NamedTuple):
    """
    Connection source from where the connection is being done
    """

    ip: str  # IP of the client
    hostname: str  # Hostname of the client

    def asDict(self) -> typing.Dict[str, str]:
        return self._asdict()
