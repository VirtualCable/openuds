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
import collections.abc

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
    type_name = _('Testing Service no cache')
    type_type = 'TestService1'
    type_description = _('Testing (and dummy) service with no cache')
    icon_file = 'service.png'

    # Functional related data

    maxUserservices = 1000  # A big number for testing purposes
    uses_cache = False
    cache_tooltip = _('None')
    uses_cache_l2 = False
    cache_tooltip_l2 = _('None')

    needs_manager = False
    must_assign_manually = False

    publication_type = None
    user_service_type = TestUserService

    def parent(self) -> 'TestProvider':
        return typing.cast('TestProvider', super().parent())

    def get_name(self) -> str:
        return self.parent().get_name() + '{' + self.type_name + '}'

    def get_basename(self) -> str:
        return self.parent().get_name()

class TestServiceCache(services.Service):
    """
    A simple testging service WITH cache and publication OFC
    """

    type_name = _('Testing Service WITH cache')
    type_type = 'TestService2'
    type_description = _('Testing (and dummy) service with CACHE and PUBLICATION')
    icon_file = 'provider.png'  # : We reuse provider icon here :-), it's just for testing purpuoses

    # Functional related data
    max_user_services = 1000  # A big number for testing
    uses_cache = True
    cache_tooltip = _('L1 cache for dummy elements')
    uses_cache_l2 = True
    cache_tooltip_l2 = _('L2 cache for dummy elements')

    needs_manager = False
    must_assign_manually = False

    # : Types of publications. In this case, we will include a publication
    # : type for this one
    # : Note that this is a MUST if you indicate that needPublication
    publication_type = TestPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = TestUserService

    def parent(self) -> 'TestProvider':
        return typing.cast('TestProvider', super().parent())

    def get_name(self) -> str:
        return self.parent().get_name() + '{' + self.type_name + '}'

    def get_basename(self) -> str:
        return self.parent().get_name()
