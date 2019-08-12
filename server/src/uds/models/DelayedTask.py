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


logger = logging.getLogger(__name__)


class DelayedTask(models.Model):
    """
    A delayed task is a kind of scheduled task. It's a task that has more than is executed at a delay
    specified at record. This is, for example, for publications, service preparations, etc...

    The delayed task is different from scheduler in the fact that they are "one shot", meaning this that when the
    specified delay is reached, the task is executed and the record is removed from the table.

    This table contains uds.core.util.jobs.DelayedTask references
    """
    type = models.CharField(max_length=128)
    tag = models.CharField(max_length=64, db_index=True)  # A tag for letting us locate delayed publications...
    instance = models.TextField()
    insert_date = models.DateTimeField()
    execution_delay = models.PositiveIntegerField()
    execution_time = models.DateTimeField(db_index=True)

    class Meta:
        """
        Meta class to declare default order and unique multiple field index
        """
        app_label = 'uds'

    def __str__(self):
        return "Run Queue task {0} owned by {3},inserted at {1} and with {2} seconds delay".format(self.type, self.insert_date, self.execution_delay, self.execution_time)
