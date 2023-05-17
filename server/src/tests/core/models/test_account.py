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
import datetime
import typing
import logging

from uds import models
from uds.core.util import model
from uds.models import consts
from uds.models.account_usage import AccountUsage

from ...fixtures import services as services_fixtures

from ...utils.test import UDSTestCase

if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

NUM_USERSERVICES = 8


class ModelAccountTest(UDSTestCase):
    user_services: typing.List['models.UserService']

    def setUp(self) -> None:
        super().setUp()
        self.user_services = services_fixtures.createCacheTestingUserServices(NUM_USERSERVICES)

    def test_base(self) -> None:
        acc = models.Account.objects.create(name='Test Account')

        self.assertEqual(acc.name, 'Test Account')
        self.assertIsInstance(acc.uuid, str)
        self.assertEqual(acc.comments, '')
        self.assertEqual(acc.time_mark, consts.NEVER)
        # Ensures no ussage accounting is done
        self.assertEqual(acc.usages.count(), 0)

    def test_start_single_userservice(self) -> None:
        acc = models.Account.objects.create(name='Test Account')
        for i in range(32):
            acc.startUsageAccounting(self.user_services[0])

            # Only one usage is createdm even with different accounters
            self.assertEqual(acc.usages.count(), 1, f'loop {i}')

        # Now create one acconting with the same user service 32 times
        # no usage is created because already created one for that user service
        for i in range(32):
            acc = models.Account.objects.create(name='Test Account')
            acc.startUsageAccounting(self.user_services[0])

            self.assertEqual(acc.usages.count(), 0, f'loop {i}')

    def test_start_single_many(self) -> None:
        acc = models.Account.objects.create(name='Test Account')
        for i in range(32):
            for i in range(NUM_USERSERVICES):
                acc.startUsageAccounting(self.user_services[i])

            # Only one usage is createdm even with different accounters
            self.assertEqual(acc.usages.count(), NUM_USERSERVICES, f'loop {i}'.format(i))

        # Now create one acconting with the same user services 32 times
        # no usage is created because already created one for that user service
        for i in range(32):
            acc = models.Account.objects.create(name='Test Account')
            for i in range(NUM_USERSERVICES):
                acc.startUsageAccounting(self.user_services[i])

            self.assertEqual(acc.usages.count(), 0, f'loop {i}')

    def test_start_multiple(self) -> None:
        for i in range(NUM_USERSERVICES):
            acc = models.Account.objects.create(name='Test Account')
            acc.startUsageAccounting(self.user_services[i])

            self.assertEqual(acc.usages.count(), 1)

    def test_end_single(self) -> None:
        acc = models.Account.objects.create(name='Test Account')
        for i in range(32):  # will create 32 usages, because we close them all, even with one user service
            acc.startUsageAccounting(self.user_services[i % NUM_USERSERVICES])
            acc.stopUsageAccounting(self.user_services[i % NUM_USERSERVICES])

            self.assertEqual(acc.usages.count(), i + 1)

    def test_end_single_many(self) -> None:
        # Now create one acconting with the same user service 32 times
        # no usage is created
        for _ in range(32):
            acc = models.Account.objects.create(name='Test Account')
            for j in range(NUM_USERSERVICES):
                acc.startUsageAccounting(self.user_services[j])
                acc.stopUsageAccounting(self.user_services[j])

            self.assertEqual(acc.usages.count(), NUM_USERSERVICES)  # This acc will only have one usage

    def test_account_usage(self) -> None:
        acc = models.Account.objects.create(name='Test Account')
        for i in range(NUM_USERSERVICES):
            usage = acc.startUsageAccounting(self.user_services[i])
            self.assertIsNotNone(usage)
            usage.start = usage.start - datetime.timedelta(seconds=32 + i)  # type: ignore
            usage.save(update_fields=['start'])  # type: ignore
            usage_end = acc.stopUsageAccounting(self.user_services[i])
            self.assertIsNotNone(usage_end)

        self.assertEqual(acc.usages.count(), NUM_USERSERVICES)
        # Elapsed time shouls be 32 seconds plus counter time
        for i, usage in enumerate(AccountUsage.objects.all().order_by('id')):
            self.assertEqual(usage.elapsed_seconds, 32 + i)
            # With timemark to NEVER, we should get 0 in elapsed_seconds_timemark
            usage.account.time_mark = consts.NEVER
            usage.account.save(update_fields=['time_mark'])
            self.assertEqual(usage.elapsed_seconds_timemark, 0)

            # And with timemark to a number AFTER end, we should get 0 in elapsed_seconds_timemark
            usage.account.time_mark = usage.end + datetime.timedelta(seconds=1)
            usage.account.save(update_fields=['time_mark'])
            self.assertEqual(usage.elapsed_seconds_timemark, 0)

            # Set acc timemark to a start + i seconds
            # This will give us only the time SINCE timemark, that is always 32 in our case
            usage.account.time_mark = usage.start + datetime.timedelta(seconds=i)
            usage.account.save(update_fields=['time_mark'])
            self.assertEqual(usage.elapsed_seconds_timemark, 32)

            # With start or end to NEVER, we should get 0 in elapsed_seconds
            usage.start = consts.NEVER
            usage.save(update_fields=['start'])
            self.assertEqual(usage.elapsed_seconds, 0)
            usage.start = model.getSqlDatetime()
            usage.end = consts.NEVER
            usage.save(update_fields=['start', 'end'])
            self.assertEqual(usage.elapsed_seconds, 0)
            # Now end is before start
            usage.start = model.getSqlDatetime()
            usage.end = usage.start - datetime.timedelta(seconds=1)
            usage.save(update_fields=['start', 'end'])
            self.assertEqual(usage.elapsed_seconds, 0)

        # Esnure elapsed and elapsed_timemark as strings
        for i, usage in enumerate(AccountUsage.objects.all().order_by('id')):
            self.assertIsInstance(usage.elapsed, str)
            self.assertIsInstance(usage.elapsed_timemark, str)
            self.assertIsInstance(str(usage), str)
