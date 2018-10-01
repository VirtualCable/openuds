# -*- coding: utf-8 -*-

#
# Copyright (c) 2018 Virtual Cable S.L.
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

from django.db import models
from django.db.models import signals

from uds.core.util import log
from uds.core.util import states
from uds.models.UUIDModel import UUIDModel
from uds.models.Tag import TaggingMixin

from uds.models.Image import Image
from uds.models.ServicesPoolGroup import ServicesPoolGroup
from uds.models.ServicesPool import ServicePool
from uds.models.Group import Group
from uds.models.Calendar import Calendar

import logging

__updated__ = '2018-10-01'

logger = logging.getLogger(__name__)


class MetaPool(UUIDModel, TaggingMixin):
    """
    A deployed service is the Service produced element that is assigned finally to an user (i.e. a Virtual Machine, etc..)
    """
    name = models.CharField(max_length=128, default='')
    short_name = models.CharField(max_length=32, default='')
    comments = models.CharField(max_length=256, default='')
    visible = models.BooleanField(default=True)
    image = models.ForeignKey(Image, null=True, blank=True, related_name='metaPools', on_delete=models.SET_NULL)
    servicesPoolGroup = models.ForeignKey(ServicesPoolGroup, null=True, blank=True, related_name='metaPools', on_delete=models.SET_NULL)
    assignedGroups = models.ManyToManyField(Group, related_name='metaPools', db_table='uds__meta_grps')

    accessCalendars = models.ManyToManyField(Calendar, related_name='accessMeta', through='CalendarAccessMeta')
    # Default fallback action for access
    fallbackAccess = models.CharField(default=states.action.ALLOW, max_length=8)

    pools = models.ManyToManyField(ServicePool, through='MetapoolMember', related_name='meta')

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds__pool_meta'
        app_label = 'uds'

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean
        toDelete = kwargs['instance']

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

    def __str__(self):
        return ''


# Connects a pre deletion signal
signals.pre_delete.connect(MetaPool.beforeDelete, sender=MetaPool)


class MetaPoolMember(UUIDModel):
    pool = models.ForeignKey(ServicePool, related_name='memberOfMeta', on_delete=models.CASCADE)
    meta_pool = models.ForeignKey(MetaPool, related_name='members', on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """
        db_table = 'uds__meta_pool_member'
        app_label = 'uds'

    def __str__(self):
        return ''
