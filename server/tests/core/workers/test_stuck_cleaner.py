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
import datetime

from ...utils.test import UDSTestCase
from ...fixtures import services as services_fixtures

from uds.models import UserService
from uds.core.types.states import State
from uds.core.workers.stuck_cleaner import StuckCleaner
from uds.core.environment import Environment

if typing.TYPE_CHECKING:
    from uds import models

logger = logging.getLogger(__name__)


class StuckCleanerTest(UDSTestCase):
    userServices: list['models.UserService']

    def setUp(self) -> None:
        StuckCleaner.setup()

        self.userServices = services_fixtures.create_db_cache_userservices(count=128)
        # Set state date of all to 2 days ago
        for i, us in enumerate(self.userServices):
            us.state_date = datetime.datetime.now() - datetime.timedelta(days=2)
            # one fourth has to_be_removed property set and state to State.PREPARING
            if i % 4 == 0:
                us.destroy_after = True  # this is a property, not a field
                us.state = State.PREPARING
                us.os_state = State.PREPARING
            # Other fourth has state to State.CANCELING
            elif i % 4 == 1:
                us.state = State.CANCELING
                us.os_state = State.PREPARING
            # Other fourth has state to State.REMOVING
            elif i % 4 == 2:
                us.state = State.REMOVING
                us.os_state = State.USABLE
            # Other fourth has state to State.USABLE (not stuck)
            elif i % 4 == 3:
                us.state = State.USABLE
                us.os_state = State.USABLE

            us.save(update_fields=['state_date', 'state', 'os_state'])

    def test_worker_outdated(self) -> None:
        count = UserService.objects.count()
        cleaner = StuckCleaner(Environment.testing_environment())
        cleaner.run()
        self.assertEqual(
            UserService.objects.count(), count // 4
        )  # 3/4 of user services should be removed

    def test_worker_not_outdated(self) -> None:
        # Fix state_date to be less than 1 day for all user services
        for us in self.userServices:
            us.state_date = datetime.datetime.now() - datetime.timedelta(
                hours=23, minutes=59
            )
            us.save(update_fields=['state_date'])
        count = UserService.objects.count()
        cleaner = StuckCleaner(Environment.testing_environment())
        cleaner.run()
        self.assertEqual(
            UserService.objects.count(), count
        )  # No service should be removed, because they are not outdated
