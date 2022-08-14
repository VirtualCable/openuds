# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import services
from uds.core.ui import gui

from .publication import TestPublication
from .deployment import TestUserDeployment


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import Provider

logger = logging.getLogger(__name__)


class ServiceTestNoCache(services.Service):
    """
    Basic testing service without cache and no publication OFC

    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    typeName = _('Testing Service no cache')
    # : Type used internally to identify this provider
    typeType = 'TestService1'
    # : Description shown at administration interface for this provider
    typeDescription = _('Testing (and dummy) service with no cache')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    iconFile = 'service.png'

    # Functional related data

    # : If the service provides more than 1 "deployed user" (-1 = no limit,
    # : 0 = ???? (do not use it!!!), N = max number to deploy
    maxDeployed = -1
    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is usesCache is True, you will need also
    # : set publicationType, do take care about that!
    usesCache = False
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cacheTooltip = _('None')
    # : If we need to generate a "Level 2" cache for this service (i.e., L1
    # : could be running machines and L2 suspended machines)
    usesCache_L2 = False
    # : Tooltip shown to user when this item is pointed at admin interface, None
    # : also because we don't use it
    cacheTooltip_L2 = _('None')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = False
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = None
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = TestUserDeployment

    def parent(self) -> 'Provider':
        return typing.cast('Provider', super().parent())

    def getName(self) -> str:
        return self.parent().getName() + '{' + self.typeName + '}'

    def getBaseName(self) -> str:
        return self.parent().getName()

class ServiceTestCache(services.Service):
    """
    A simple testging service WITH cache and publication OFC
    """

    typeName = _('Testing Service WITH cache')
    typeType = 'TestService2'
    typeDescription = _('Testing (and dummy) service with CACHE and PUBLICATION')
    iconFile = 'provider.png'  # : We reuse provider icon here :-), it's just for testing purpuoses

    # Functional related data
    maxDeployed = -1
    usesCache = True
    cacheTooltip = _('L1 cache for dummy elements')
    usesCache_L2 = True
    cacheTooltip_L2 = _('L2 cache for dummy elements')

    needsManager = False
    mustAssignManually = False

    # : Types of publications. In this case, we will include a publication
    # : type for this one
    # : Note that this is a MUST if you indicate that needPublication
    publicationType = TestPublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = TestUserDeployment

    def parent(self) -> 'Provider':
        return typing.cast('Provider', super().parent())

    def getName(self) -> str:
        return self.parent().getName() + '{' + self.typeName + '}'

    def getBaseName(self) -> str:
        return self.parent().getName()
