# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

__updated__ = '2015-03-01'

from uds.models import Provider, Service, OSManager, Transport, Network, ServicePool, UserService, Authenticator, User, Group, StatsCounters, StatsEvents
import logging

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


def getObjectType(obj):
    return {
        Provider: PROVIDER_TYPE,
        Service: SERVICE_TYPE,
        OSManager: OSMANAGER_TYPE,
        Transport: TRANSPORT_TYPE,
        Network: NETWORK_TYPE,
        ServicePool: POOL_TYPE,
        UserService: USER_SERVICE_TYPE,
        Authenticator: AUTHENTICATOR_TYPE,
        User: USER_TYPE,
        Group: GROUP_TYPE,
        StatsCounters: STATS_COUNTER_TYPE,
        StatsEvents: STATS_EVENTS_TYPE
    }.get(type(obj))
