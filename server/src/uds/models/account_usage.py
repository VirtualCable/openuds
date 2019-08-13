# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging

from django.db import models

from uds.core.util.tools import secondsToTimeString

from .uuid_model import UUIDModel
from .account import Account
from .user_service import UserService
from .util import NEVER


logger = logging.getLogger(__name__)


class AccountUsage(UUIDModel):
    """
    AccountUsage storing on DB model
    This is intended for small images (i will limit them to 128x128), so storing at db is fine

    """
    user_name = models.CharField(max_length=128, db_index=True, default='')
    user_uuid = models.CharField(max_length=50, db_index=True, default='')
    pool_name = models.CharField(max_length=128, db_index=True, default='')
    pool_uuid = models.CharField(max_length=50, db_index=True, default='')
    start = models.DateTimeField(default=NEVER)
    end = models.DateTimeField(default=NEVER)
    user_service = models.OneToOneField(UserService, null=True, blank=True, related_name='accounting', on_delete=models.SET_NULL)

    account = models.ForeignKey(Account, related_name='usages', on_delete=models.CASCADE)

    class Meta:
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds_acc_usage'
        app_label = 'uds'

    @property
    def elapsed_seconds(self) -> int:
        if  NEVER in (self.end, self.start):
            return 0
        return (self.end - self.start).total_seconds()

    @property
    def elapsed_seconds_timemark(self) -> int:
        if  NEVER in (self.end, self.start):
            return 0

        start = self.start
        end = self.end
        if start < self.account.time_mark:
            start = self.account.time_mark
        if end < start:
            return 0

        return (end - start).total_seconds()

    @property
    def elapsed(self) -> str:
        return secondsToTimeString(self.elapsed_seconds)

    @property
    def elapsed_timemark(self) -> str:
        return secondsToTimeString(self.elapsed_seconds_timemark)

    def __str__(self):
        return 'AccountUsage id {}, pool {}, name {}, start {}, end {}'.format(self.id, self.pool_name, self.user_name, self.start, self.end)
