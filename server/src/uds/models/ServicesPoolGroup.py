# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

from __future__ import unicode_literals

from django.db import models
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible

from uds.models.UUIDModel import UUIDModel
from uds.models.Image import Image

import logging

__updated__ = '2016-02-12'


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class ServicesPoolGroup(UUIDModel):
    '''
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    '''
    # pylint: disable=model-missing-unicode
    name = models.CharField(max_length=128, default='')
    comments = models.CharField(max_length=256, default='')
    image = models.ForeignKey(Image, null=True, blank=True, related_name='servicesPoolsGrou', on_delete=models.SET_NULL)

    class Meta(UUIDModel.Meta):
        '''
        Meta class to declare the name of the table at database
        '''
        db_table = 'uds__pools_groups'
        app_label = 'uds'

    def __str__(self):
        return u"Service Pool group {0}({1})".format(self.name, self.comments)

