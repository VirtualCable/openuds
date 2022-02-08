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
from re import I
import typing

from django.db import models

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.alerts import notifier


class Notifier(ManagedObjectModel, TaggingMixin):

    NOTIFIER_LEVEL_INFO = 'INFO'
    NOTIFIER_LEVEL_WARNING = 'WARNING'
    NOTIFIER_LEVEL_ERROR = 'ERROR'
    NOTIFIER_LEVEL_CRITICAL = 'CRITICAL'

    NOTIFIER_LEVEL_CHOICES = (
        (NOTIFIER_LEVEL_INFO, 'Info'),
        (NOTIFIER_LEVEL_WARNING, 'Warning'),
        (NOTIFIER_LEVEL_ERROR, 'Error'),
        (NOTIFIER_LEVEL_CRITICAL, 'Critical'),
    )

    name = models.CharField(max_length=128, default='')
    comments = models.CharField(max_length=256, default='')
    enabled = models.BooleanField(default=True)
    level = models.CharField(
        max_length=16,
        choices=NOTIFIER_LEVEL_CHOICES,
        default=NOTIFIER_LEVEL_ERROR
    )

    class Meta:
        """
        Meta class to declare db table
        """

        db_table = 'uds_notifier'
        app_label = 'uds'

    def getInstance(
        self, values: typing.Optional[typing.Dict[str, str]] = None
    ) -> 'notifier.Notifier':
        return typing.cast('notifier.Notifier', super().getInstance(values=values))
