# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import typing
import collections.abc
import logging

from django.db import models

from uds.core.util.utils import secondsToTimeString

from .uuid_model import UUIDModel
from .account import Account
from .user_service import UserService
from ..core.consts import NEVER

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService, Account

logger = logging.getLogger(__name__)


# pylint: disable=no-member  # pylint complais a lot about members of models...
class AccountUsage(UUIDModel):
    """
    AccountUsage storing on DB model
    """

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["AccountUsage"]'

    user_name = models.CharField(max_length=128, db_index=True, default='')
    user_uuid = models.CharField(max_length=50, db_index=True, default='')
    pool_name = models.CharField(max_length=128, db_index=True, default='')
    pool_uuid = models.CharField(max_length=50, db_index=True, default='')
    start = models.DateTimeField(default=NEVER)
    end = models.DateTimeField(default=NEVER)
    user_service = models.OneToOneField(
        UserService,
        null=True,
        blank=True,
        related_name='accounting',
        on_delete=models.SET_NULL,
    )
    account = models.ForeignKey(
        Account, related_name='usages', on_delete=models.CASCADE
    )

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_acc_usage'
        app_label = 'uds'

    @property
    def elapsed_seconds(self) -> int:
        if NEVER in (self.end, self.start) or self.end < self.start:
            return 0
        return int((self.end - self.start).total_seconds())

    @property
    def elapsed_seconds_timemark(self) -> int:
        if NEVER in (self.end, self.start, self.account.time_mark):
            return 0

        start = self.start
        end = self.end
        if start < self.account.time_mark:
            start = self.account.time_mark
        if end < start:
            return 0

        return int((end - start).total_seconds())

    @property
    def elapsed(self) -> str:
        return secondsToTimeString(self.elapsed_seconds)

    @property
    def elapsed_timemark(self) -> str:
        return secondsToTimeString(self.elapsed_seconds_timemark)

    def __str__(self):
        return f'AccountUsage id {self.id}, pool {self.pool_name}, name {self.user_name}, start {self.start}, end {self.end}'
