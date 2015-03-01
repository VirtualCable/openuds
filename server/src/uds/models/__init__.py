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

__updated__ = '2015-03-01'

import logging

logger = logging.getLogger(__name__)


# Permissions
from .Permissions import Permissions

# Utility
from .Util import getSqlDatetime
from .Util import optimizeTable
from .Util import NEVER
from .Util import NEVER_UNIX

# Services
from .Provider import Provider
from .Service import Service

# Os managers
from .OSManager import OSManager

# Transports
from .Transport import Transport
from .Network import Network


# Authenticators
from .Authenticator import Authenticator
from .User import User
from .UserPreference import UserPreference
from .Group import Group


# Provisioned services
from .ServicesPool import DeployedService  # Old name, will continue here for a while already
from .ServicesPool import ServicePool  # New name
from .ServicesPoolPublication import DeployedServicePublication
from .UserService import UserService
from .UserServiceProperty import UserServiceProperty

# Especific log information for an user service
from .Log import Log

# Stats
from .StatsCounters import StatsCounters
from .StatsEvents import StatsEvents


# General utility models, such as a database cache (for caching remote content of slow connections to external services providers for example)
# We could use django cache (and maybe we do it in a near future), but we need to clean up things when objecs owning them are deleted
from .Cache import Cache
from .Config import Config
from .Storage import Storage
from .UniqueId import UniqueId

# Workers/Schedulers related
from .Scheduler import Scheduler
from .DelayedTask import DelayedTask

# Image galery related
from .Image import Image