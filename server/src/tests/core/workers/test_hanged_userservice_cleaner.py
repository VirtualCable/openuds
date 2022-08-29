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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import typing

from uds import models
from uds.core.environment import Environment
from uds.core.util import config
from uds.core.util.state import State
from uds.core.workers.hanged_userservice_cleaner import HangedCleaner

from ...utils.test import UDSTransactionTestCase
from ...fixtures import services as fixtures_services

MAX_INIT = 300
TEST_SERVICES = 5 * 5  # Ensure multiple of 5 for testing


class HangedCleanerTests(UDSTransactionTestCase):
    userServices: typing.List[models.UserService]

    def setUp(self):
        config.GlobalConfig.MAX_INITIALIZING_TIME.set(MAX_INIT)
        config.GlobalConfig.MAX_REMOVAL_TIME.set(MAX_INIT)
        HangedCleaner.setup()
        # All created user services has "in_use" to False, os_state and state to USABLE
        self.userServices = fixtures_services.newUserServiceForTesting(
            count=TEST_SERVICES
        )

        # Setup a few user services as hanged
        for i, us in enumerate(self.userServices):
            if i % 5 == 0:
                us.state = (
                    State.PREPARING
                )  # These will convert in "CANCELED" (first CANCELING but TestDeployment Cancels inmediately, so it will be CANCELED)
            elif i % 5 == 1:
                us.state = State.USABLE
                us.os_state = State.PREPARING  # THese in "REMOVABLE"
            elif i % 5 == 2:
                us.state = State.REMOVING  # These will be set "REMOVABLE" to retry
            elif i % 5 == 3:
                us.state = State.CANCELING  # These will be set "REMOVABLE" to retry
            else:
                # Just for setting defaults, that already are defaults :)
                us.state = State.USABLE
                us.os_state = State.USABLE

            us.state_date = models.getSqlDatetime() - datetime.timedelta(
                seconds=MAX_INIT + 1
            )
            us.save(update_fields=['state', 'os_state', 'state_date'])

    def test_hanged_cleaner(self):
        # At start, there is no "removable" user services
        cleaner = HangedCleaner(Environment.getTempEnv())
        cleaner.run()
        one_fith = TEST_SERVICES // 5
        self.assertEqual(
            models.UserService.objects.filter(state=State.CANCELED).count(), one_fith
        )
        self.assertEqual(
            models.UserService.objects.filter(state=State.REMOVABLE).count(), 3*one_fith
        )
        self.assertEqual(
            models.UserService.objects.filter(state=State.USABLE).count(), one_fith
        )
