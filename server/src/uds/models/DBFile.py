# -*- coding: utf-8 -*-

# Model based on https://github.com/llazzaro/django-scheduler
#
# Copyright (c) 2016 Virtual Cable S.L.
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

from __future__ import unicode_literals

__updated__ = '2018-03-02'

from django.db import models
from django.utils.encoding import python_2_unicode_compatible
from uds.models.UUIDModel import UUIDModel
from uds.core.util import encoders

import logging
import six

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class DBFile(UUIDModel):
    owner = models.CharField(max_length=32, default='')  # Not indexed, used for cleanups only
    name = models.CharField(max_length=255, primary_key=True)
    content = models.TextField(blank=True)
    size = models.IntegerField(default=0)
    created = models.DateTimeField()
    modified = models.DateTimeField()

    @property
    def data(self):
        try:
            return encoders.decode(encoders.decode(self.content, 'base64'), 'zip')
        except Exception:
            logger.error('DBFile {} has errors and cannot be used'.format(self.name))
            try:
                self.delete()  # Autodelete, invalid...
                pass
            except Exception:
                logger.error('Could not even delete {}!!'.format(self.name))

            return ''

    @data.setter
    def data(self, value):
        self.size = len(value)
        content = encoders.encode(encoders.encode(value, 'zip'), 'base64', asText=True)
        self.content = content

    def __str__(self):
        return 'File: {} {} {} {}'.format(self.name, self.size, self.created, self.modified)
