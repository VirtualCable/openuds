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

from uds.core.util.model import generateUuid


logger = logging.getLogger(__name__)


class UUIDModel(models.Model):
    """
    Base abstract model for models that require an uuid
    """

    uuid = models.CharField(max_length=50, unique=True, default=generateUuid)

    # Automatic field from Model without a defined specific primary_key
    # Just a fake declaration to allow type checking
    id: int

    class Meta:  # pylint: disable=too-few-public-methods
        abstract = True

    def genUuid(self) -> str:
        return generateUuid()

    # Override default save to add uuid
    def save(self, *args, **kwargs):
        if not self.uuid:
            self.uuid = self.genUuid()
        elif self.uuid != self.uuid.lower():
            self.uuid = (
                self.uuid.lower()
            )  # If we modify uuid elsewhere, ensure that it's stored in lower case

        if 'update_fields' in kwargs:
            kwargs['update_fields'] = list(kwargs['update_fields']) + ['uuid']

        return models.Model.save(self, *args, **kwargs)
