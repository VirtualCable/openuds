# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

__updated__ = '2014-11-04'

import logging

logger = logging.getLogger(__name__)


# Utility
from uds.models.Util import getSqlDatetime
from uds.models.Util import optimizeTable
from uds.models.Util import NEVER
from uds.models.Util import NEVER_UNIX

# Services
from uds.models.Provider import Provider
from uds.models.Service import Service

# Os managers
from uds.models.OSManager import OSManager

# Transports
from uds.models.Transport import Transport
from uds.models.Network import Network


# Authenticators
from uds.models.Authenticator import Authenticator
from uds.models.User import User
from uds.models.UserPreference import UserPreference
from uds.models.Group import Group


# Provisioned services
from uds.models.ServicesPool import DeployedService  # Old name, will continue here for a while already
from uds.models.ServicesPool import ServicePool  # New name
from uds.models.ServicesPoolPublication import DeployedServicePublication
from uds.models.UserService import UserService

# Especific log information for an user service
from uds.models.Log import Log

# Stats
from uds.models.StatsCounters import StatsCounters
from uds.models.StatsEvents import StatsEvents


# General utility models, such as a database cache (for caching remote content of slow connections to external services providers for example)
# We could use django cache (and maybe we do it in a near future), but we need to clean up things when objecs owning them are deleted
from uds.models.Cache import Cache
from uds.models.Config import Config
from uds.models.Storage import Storage
from uds.models.UniqueId import UniqueId

# Workers/Schedulers related
from uds.models.Scheduler import Scheduler
from uds.models.DelayedTask import DelayedTask

# Image galery related
from uds.models.Image import Image