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

from uds.REST.handlers import AUTH_TOKEN_HEADER
from uds.REST.methods.actor_v3 import MANAGED, UNMANAGED, ALLOWED_FAILS

from ..utils import rest

logger = logging.getLogger(__name__)


class SystemTest(rest.test.RESTTestCase):
    def test_overview(self):
        # If not logged in, will fail
        response = self.client.get('/uds/rest/system/overview')
        self.assertEqual(response.status_code, 403)

        # Login as admin
        self.login()

        # Now, will work
        response = self.client.get('/uds/rest/system/overview')
        self.assertEqual(response.status_code, 200)
        json = response.json()
        # should have rest.test.NUMBER_OF_ITEMS_TO_CREATE * 3 users (admins, staff and plain users),
        # rest.test.NUMBER_OF_ITEMS_TO_CREATE groups
        # 2 services (1 managed, 1 unmanaged), 2 service_pools (1 for each service), 2 user_services (1 for each service pool)
        # no meta_pools, and no restrained_services_pools
        self.assertEqual(json['users'], rest.test.NUMBER_OF_ITEMS_TO_CREATE * 3)
        self.assertEqual(json['groups'], rest.test.NUMBER_OF_ITEMS_TO_CREATE)
        self.assertEqual(json['services'], 2)
        self.assertEqual(json['service_pools'], 2)
        self.assertEqual(json['user_services'], 2)
        self.assertEqual(json['meta_pools'], 0)
        self.assertEqual(json['restrained_services_pools'], 0)

        
    def test_charts(self):
        pass
