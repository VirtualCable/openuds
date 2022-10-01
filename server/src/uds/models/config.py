# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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


class Config(models.Model):
    """
    General configuration values model. Used to store global and specific modules configuration values.
    This model is managed via uds.core.util.config.Config class
    """

    section = models.CharField(max_length=128, db_index=True)
    key = models.CharField(max_length=64, db_index=True)
    value = models.TextField(default='')
    crypt = models.BooleanField(default=False)
    long = models.BooleanField(default=False)
    field_type = models.IntegerField(default=-1)
    help = models.CharField(max_length=256, default='')

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Config]'

    class Meta:
        """
        Meta class to declare default order and unique multiple field index
        """

        db_table = 'uds_configuration'
        constraints = [
            models.UniqueConstraint(fields=['section', 'key'], name='u_cfg_section_key')
        ]

        app_label = 'uds'

    def __str__(self) -> str:
        return "Config {} = {}".format(self.key, self.value)
