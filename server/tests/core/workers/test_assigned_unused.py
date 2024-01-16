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
import datetime

from uds import models
from uds.core.util import model
from uds.core.environment import Environment
from uds.core.util import config
from uds.core.types.states import State
from uds.core.workers.assigned_unused import AssignedAndUnused

from ...utils.test import UDSTestCase
from ...fixtures import services as fixtures_services


class AssignedAndUnusedTest(UDSTestCase):
    userServices: list[models.UserService]

    def setUp(self):
        config.GlobalConfig.CHECK_UNUSED_TIME.set('600')
        AssignedAndUnused.setup()
        # All created user services has "in_use" to False, os_state and state to USABLE
        self.userServices = fixtures_services.create_cache_testing_userservices(count=32)

    def test_assigned_unused(self):
        for us in self.userServices:  # Update state date to now
            us.set_state(State.USABLE)
        # Set now, should not be removed
        count = models.UserService.objects.filter(state=State.REMOVABLE).count()
        cleaner = AssignedAndUnused(Environment.get_temporary_environment())
        # since_state = util.sql_datetime() - datetime.timedelta(seconds=cleaner.frecuency)
        cleaner.run()
        self.assertEqual(models.UserService.objects.filter(state=State.REMOVABLE).count(), count)
        # Set half the userServices to a long-ago state, should be removed
        for i, us in enumerate(self.userServices):
            if i%2 == 0:
                us.state_date = model.sql_datetime() - datetime.timedelta(seconds=602)
                us.save(update_fields=['state_date'])
        cleaner.run()
        self.assertEqual(models.UserService.objects.filter(state=State.REMOVABLE).count(), count + len(self.userServices)//2)
