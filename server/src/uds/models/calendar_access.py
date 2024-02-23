# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
#
# Copyright (c) 2016-2023 Virtual Cable S.L.U.
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
import logging

from django.db import models


from uds.core import types
from .uuid_model import UUIDModel
from .calendar import Calendar
from .service_pool import ServicePool
from .meta_pool import MetaPool


logger = logging.getLogger(__name__)


class CalendarAccess(UUIDModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    service_pool = models.ForeignKey(
        ServicePool, related_name='calendarAccess', on_delete=models.CASCADE
    )
    access = models.CharField(max_length=8, default=types.states.State.DENY)
    priority = models.IntegerField(default=0, db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[CalendarAccess]'

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_cal_access'
        ordering = ('priority',)
        app_label = 'uds'

    def __str__(self) -> str:
        return f'Calendar Access {self.calendar}/{self.access}'


class CalendarAccessMeta(UUIDModel):
    calendar = models.ForeignKey(Calendar, on_delete=models.CASCADE)
    meta_pool = models.ForeignKey(MetaPool, related_name='calendarAccess', on_delete=models.CASCADE)
    access = models.CharField(max_length=8, default=types.states.State.DENY)
    priority = models.IntegerField(default=0, db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.BaseManager[CalendarAccessMeta]'

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_cal_maccess'
        ordering = ('priority',)
        app_label = 'uds'

    def __str__(self) -> str:
        return f'Calendar Access Meta {self.calendar}/{self.access}'
