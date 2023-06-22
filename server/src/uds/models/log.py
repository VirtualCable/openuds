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
import logging

from django.db import models

logger = logging.getLogger(__name__)


class Log(models.Model):
    """Log model associated with an object.

    This log is mainly used to keep track of log relative to objects
    (such as when a user access a machine, or information related to user logins/logout, errors, ...)

    Note:
        owner_id can be 0, in wich case, the log is global (not related to any object)

        if owner id is 0, these are valid owner_type values:
            -1: Global log
            -2: AUDIT log
        See :py:mod:`uds.core.util.log` for more information
    """

    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)

    created = models.DateTimeField(db_index=True)
    source = models.CharField(max_length=16, default='internal', db_index=True)
    level = models.PositiveIntegerField(default=0, db_index=True)
    name = models.CharField(max_length=64, default='')  # If syslog, log name, else empty
    data = models.CharField(max_length=4096, default='')

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Log]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_log'
        app_label = 'uds'

    @property
    def level_str(self) -> str:
        # pylint: disable=import-outside-toplevel
        from uds.core.util.log import LogLevel

        return LogLevel.fromInt(self.level).name

    def __str__(self) -> str:
        return (
            f'Log of {self.owner_type}({self.owner_id}):'
            f' {self.created} - {self.source} - {self.level} - {self.data}'
        )
