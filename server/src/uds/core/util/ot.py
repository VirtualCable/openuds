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

from uds import models

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

# Constants for each type
PROVIDER_TYPE = 1
SERVICE_TYPE = 2
OSMANAGER_TYPE = 3
TRANSPORT_TYPE = 4
NETWORK_TYPE = 5
POOL_TYPE = 6
USER_SERVICE_TYPE = 7
AUTHENTICATOR_TYPE = 8
USER_TYPE = 9
GROUP_TYPE = 10
STATS_COUNTER_TYPE = 11
STATS_EVENTS_TYPE = 12
CALENDAR_TYPE = 13
CALENDAR_RULE_TYPE = 14
PROXY_TYPE = 16
METAPOOL_TYPE = 15
ACCOUNT_TYPE = 16
ACTOR_TOKEN_TYPE = 17
TUNNEL_TOKEN_TYPE = 18

objTypeDict: typing.Dict[typing.Type, int] = {
    models.Provider: PROVIDER_TYPE,
    models.Service: SERVICE_TYPE,
    models.OSManager: OSMANAGER_TYPE,
    models.Transport: TRANSPORT_TYPE,
    models.Network: NETWORK_TYPE,
    models.ServicePool: POOL_TYPE,
    models.UserService: USER_SERVICE_TYPE,
    models.Authenticator: AUTHENTICATOR_TYPE,
    models.User: USER_TYPE,
    models.Group: GROUP_TYPE,
    models.StatsCounters: STATS_COUNTER_TYPE,
    models.StatsEvents: STATS_EVENTS_TYPE,
    models.Calendar: CALENDAR_TYPE,
    models.CalendarRule: CALENDAR_RULE_TYPE,
    models.Proxy: PROXY_TYPE,
    models.MetaPool: METAPOOL_TYPE,
    models.Account: ACCOUNT_TYPE,
    models.ActorToken: ACTOR_TOKEN_TYPE,
    models.TunnelToken: TUNNEL_TOKEN_TYPE,
}


def getObjectType(obj: 'Model') -> typing.Optional[int]:
    return objTypeDict.get(type(obj))
