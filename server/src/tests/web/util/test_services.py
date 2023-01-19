# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# We use commit/rollback
import typing
from unittest import mock

from uds.web.util import services
import uds.core.util.os_detector as osd

from ...utils.test import UDSTransactionTestCase
from ...fixtures import authenticators as fixtures_authenticators
from ...fixtures import services as fixtures_services


class TestGetServicesData(UDSTransactionTestCase):
    def test_cache(self):
        # We need to create a user with some services
        auth = fixtures_authenticators.createAuthenticator()
        groups = fixtures_authenticators.createGroups(auth, 3)
        user = fixtures_authenticators.createUsers(auth, 1, groups=groups)[0]

        # Create 10 services, for this user
        for i in range(10):
            fixtures_services.createCacheTestingUserServices(count=1, user=user, groups=groups)

        request = mock.Mock()
        request.user = user
        request.authorized = True
        request.session = {}
        request.ip = '127.0.0.1'
        request.ip_version = 4
        request.ip_proxy = '127.0.0.1'
        request.os = osd.DetectedOsInfo(osd.KnownOS.Linux, osd.KnownBrowser.Firefox, 'Windows 10')

        data = services.getServicesData(request)
        # Will return this:
        #  return {
        #     'services': services,
        #     'ip': request.ip,
        #     'nets': nets,
        #     'transports': validTrans,
        #     'autorun': autorun,
        # }
        self.assertEqual(len(data['services']), 10)
        self.assertEqual(data['ip'], '127.0.0.1')
        self.assertEqual(len(data['nets']), 0)
        self.assertEqual(len(data['transports']), 0)
        self.assertEqual(data['autorun'], 0)

        # Check services data
        # Every service is returned like this:
        # return {
        #     'id': ('M' if is_meta else 'F') + uuid,
        #     'is_meta': is_meta,
        #     'name': name,
        #     'visual_name': visual_name,
        #     'description': description,
        #     'group': group,
        #     'transports': transports,
        #     'imageId': image and image.uuid or 'x',
        #     'show_transports': show_transports,
        #     'allow_users_remove': allow_users_remove,
        #     'allow_users_reset': allow_users_reset,
        #     'maintenance': maintenance,
        #     'not_accesible': not_accesible,
        #     'in_use': in_use,
        #     'to_be_replaced': to_be_replaced,
        #     'to_be_replaced_text': to_be_replaced_text,
        #     'custom_calendar_text': custom_calendar_text,
        # }



