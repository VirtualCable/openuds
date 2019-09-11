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
from django.utils.translation import ugettext as _

from uds.core.ui.images import DEFAULT_THUMB_BASE64

from .uuid_model import UUIDModel
from .image import Image


logger = logging.getLogger(__name__)


class ServicePoolGroup(UUIDModel):
    """
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    """
    # pylint: disable=model-missing-unicode
    name = models.CharField(max_length=128, default='', db_index=True, unique=True)
    comments = models.CharField(max_length=256, default='')
    priority = models.IntegerField(default=0, db_index=True)
    image: Image = models.ForeignKey(Image, null=True, blank=True, related_name='servicesPoolsGroup', on_delete=models.SET_NULL)

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds__pools_groups'
        app_label = 'uds'

    def __str__(self):
        return 'Service Pool group {}({})'.format(self.name, self.comments)

    @property
    def as_dict(self):
        return {
            'id': self.uuid,
            'name': self.name,
            'comments': self.comments,
            'priority': self.priority,
            'imageUuid': self.image.uuid if self.image is not None else 'x'
        }

    @property
    def thumb64(self):
        return self.image.thumb64 if self.image is not None else  DEFAULT_THUMB_BASE64

    @staticmethod
    def default():
        return ServicePoolGroup(name=_('General'), comments='', priority=-10000)
