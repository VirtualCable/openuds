# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.
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

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.ui.user_interface import gui, UDSB, UDSK
from uds.core.environment import Environment

from uds.services.Proxmox.provider import ProxmoxProvider

from django.conf import settings


from uds.services.Vmware_enterprise import service_linked, provider

PROVIDER_SERIALIZE_DATA: typing.Final[str] = (
    'R1VJWgF2MRKGpo40r0qAyiorr5SEbg/cXmhQPC9zfAFccS20LF2du6+QhrCna7WykmcPW95FHOLWwEBpuYc3Fdh4Id'
    '/jIs/hyWb/0f+30JduzD2Bjpgop+wO8sdXpy1/MilpVYKOycbGJ8JxNGov0zU4kw6FWpRD6MiCXaGBvQrzLmMFY78D'
    '25y0YtOV6RhP+KKp1AUiEvS9bqGogiFuGrxq/bqI+at1CgLHXn0OK0ZSqLUroOizDu+3PNoMHC2lqbgO8CRIPVf0Cz'
    '1/ZEyvJ44PCeOZZKLqzxhgbikL4g8GJptBAIMVedVMdxjpTo5oWS3O9TCtSB51iXkqpOjP7UFmUUQmsYe7/7CkHM8g'
    '3y30ZN/lgB5pr5GSrfAwXKsxwNZ9cKAzm3G/xVtYpm69zcmNGWE+md+aGhGDBOVBCyvE9AkFsFdZ'
)


class ProxmoxUserInterface(UDSTestCase):
    def test_provider_userinterface(self) -> None:
        provider = ProxmoxProvider(environment=Environment.get_temporary_environment())
        provider.deserialize(PROVIDER_SERIALIZE_DATA)
