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


class UniqueId(models.Model):
    """
    Unique ID Database. Used to store unique names, unique macs, etc...
    Managed via uds.core.util.unique_id_generator.unique_id_generator
    """

    owner = models.CharField(max_length=128, db_index=True, default='')
    basename = models.CharField(max_length=32, db_index=True)
    seq = models.BigIntegerField(db_index=True)
    assigned = models.BooleanField(db_index=True, default=True)
    stamp = models.IntegerField(db_index=True, default=0)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[UniqueId]'

    class Meta: # pyright: ignore
        """
        Meta class to declare default order and unique multiple field index
        """

        ordering = ('-seq',)
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(fields=['basename', 'seq'], name='u_uid_base_seq')
        ]

    def __str__(self) -> str:
        return f'{self.owner} {self.basename}.{self.seq}, assigned is {self.assigned}'
