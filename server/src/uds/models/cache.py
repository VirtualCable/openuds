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
from datetime import timedelta
import logging

from django.db import models, transaction

from ..core.util.model import sql_datetime


logger = logging.getLogger(__name__)


class Cache(models.Model):
    """
    General caching model. This model is managed via uds.core.util.cache.Cache class
    """

    owner = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, primary_key=True)
    value = models.TextField(default='')
    # Date creation or validation of this entry. Set at write time
    created = models.DateTimeField()
    validity = models.IntegerField(default=60)  # Validity of this entry, in seconds

    # "fake" relations declarations for type checking
    # objects: 'models.manager.Manager[Cache]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds_utility_cache'
        app_label = 'uds'

    @staticmethod
    def cleanUp() -> None:
        """
        Purges the cache items that are no longer vaild.
        """
        now = sql_datetime()
        with transaction.atomic():
            for v in Cache.objects.all():
                if now > v.created + timedelta(seconds=v.validity):
                    v.delete()

    def __str__(self):
        if sql_datetime() > (self.created + timedelta(seconds=self.validity)):
            expired = "Expired"
        else:
            expired = "Active"
        return f'{self.owner} {self.key} = {self.value} ({expired})'
