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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from uds import models
from uds.core.util import properties

from ...fixtures import services as services_fixtures
from ...utils.test import UDSTestCase

logger = logging.getLogger(__name__)

NUM_USERSERVICES = 8


class PropertiesTest(UDSTestCase):
    user_services: list['models.UserService']

    def setUp(self) -> None:
        super().setUp()
        self.user_services = []
        for i in range(NUM_USERSERVICES):
            # So we have 8 userservices, each one with a different user
            self.user_services.extend(services_fixtures.create_db_cache_userservices())

    def testUserServiceProperty(self) -> None:
        """
        Test that properties are stored and retrieved for user services
        """
        for i, us in enumerate(self.user_services):
            key, value = 'key{}'.format(i), 'value{}'.format(i)
            
            # Test as context manager
            with us.properties as p:
                p[key] = value
            with us.properties as p:
                self.assertEqual(p[key], value)

            prop = models.Properties.objects.get(owner_id=us.uuid, owner_type='userservice', key=key)
            self.assertEqual(prop.value, value)
            
            # Test as property
            key, value = 'keyx{}'.format(i), 'valuex{}'.format(i)
            us.properties[key] = value
            self.assertEqual(us.properties[key], value)
            
            prop = models.Properties.objects.get(owner_id=us.uuid, owner_type='userservice', key=key)
            self.assertEqual(prop.value, value)
        
    