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
import logging

from django.conf import settings

from uds import models
from uds.REST.handlers import AUTH_TOKEN_HEADER

from ..utils import rest, constants


logger = logging.getLogger(__name__)


class ActorRegisterV3(rest.test.RESTTestCase):
    """
    Test actor functionality
    """

    def test_register(self) -> None:
        """
        Test actor rest api registration
        """
        response: typing.Any
        for i, usr in enumerate(self.admins + self.staffs + self.plain_users):
            token = self.login(usr)

            # Try to register. Plain users will fail
            will_fail = usr in self.plain_users
            response = self.client.post(
                '/uds/rest/actor/v3/register',
                data=self.register_data(
                    constants.STRING_CHARS if i % 2 == 0 else constants.STRING_CHARS_INVALID
                ),
                content_type='application/json',
                **{AUTH_TOKEN_HEADER: token}
            )
            if will_fail:
                self.assertEqual(response.status_code, 403)
                continue  # Try next user, this one will fail

            self.assertEqual(response.status_code, 200)
            token = response.json()['result']

            # Ensure database contains the registered token
            self.assertEqual(models.ActorToken.objects.filter(token=token).count(), 1)
