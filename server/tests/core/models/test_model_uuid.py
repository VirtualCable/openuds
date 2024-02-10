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
import typing
import collections.abc
import logging

from ...utils.test import UDSTestCase
from ...fixtures import authenticators as authenticators_fixtures
from uds import models

if typing.TYPE_CHECKING:
    pass

class ModelUUIDTest(UDSTestCase):
    auth: 'models.Authenticator'
    user: 'models.User'
    group: 'models.Group'

    def setUp(self) -> None:
        super().setUp()
        self.auth = authenticators_fixtures.create_authenticator()
        self.group = authenticators_fixtures.create_groups(self.auth, 1)[0]
        self.user = authenticators_fixtures.create_users(self.auth, 1, groups=[self.group])[0]
    
    def test_uuid_lowercase(self):
        """
        Tests that uuids are always lowercase
        """
        # Change user uuid to uppercase
        self.user.uuid = self.user.uuid.upper()
        self.user.save()
        self.assertEqual(self.user.uuid, self.user.uuid.lower())

    def test_uuid_regenerated(self) -> None:
        """
        Tests that uuids are regenerated when user is saved
        """
        self.user.uuid = ''
        self.user.save()
        self.assertNotEqual(None, self.user.uuid)

    def test_uuidmodel_str(self) -> None:
        """
        Tests that uuids are regenerated when user is saved
        """
        self.assertIsInstance(str(self.user), str)
