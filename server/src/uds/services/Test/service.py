# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import services
from uds.core.ui import gui

from .publication import TestPublication
from .deployment import TestUserService


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import TestProvider

logger = logging.getLogger(__name__)


class TestServiceNoCache(services.Service):
    """
    Basic testing service without cache and no publication OFC
    """
    typeName = _('Testing Service no cache')
    typeType = 'TestService1'
    typeDescription = _('Testing (and dummy) service with no cache')
    iconFile = 'service.png'

    # Functional related data

    maxUserservices = 1000  # A big number for testing purposes
    usesCache = False
    cacheTooltip = _('None')
    usesCache_L2 = False
    cacheTooltip_L2 = _('None')

    needsManager = False
    mustAssignManually = False

    publicationType = None
    userServiceType = TestUserService

    def parent(self) -> 'TestProvider':
        return typing.cast('TestProvider', super().parent())

    def getName(self) -> str:
        return self.parent().getName() + '{' + self.typeName + '}'

    def getBaseName(self) -> str:
        return self.parent().getName()

class TestServiceCache(services.Service):
    """
    A simple testging service WITH cache and publication OFC
    """

    typeName = _('Testing Service WITH cache')
    typeType = 'TestService2'
    typeDescription = _('Testing (and dummy) service with CACHE and PUBLICATION')
    iconFile = 'provider.png'  # : We reuse provider icon here :-), it's just for testing purpuoses

    # Functional related data
    maxUserServices = 1000  # A big number for testing
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
    userServiceType = TestUserService

    def parent(self) -> 'TestProvider':
        return typing.cast('TestProvider', super().parent())

    def getName(self) -> str:
        return self.parent().getName() + '{' + self.typeName + '}'

    def getBaseName(self) -> str:
        return self.parent().getName()
