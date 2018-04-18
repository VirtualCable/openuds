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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

from __future__ import unicode_literals

from django.db import models
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible


from uds.core.util.State import State
from uds.core.util import log
from .UUIDModel import UUIDModel

from .Authenticator import Authenticator
from .User import User
from .Util import UnsavedForeignKey, getSqlDatetime

import logging

logger = logging.getLogger(__name__)

__updated__ = '2015-09-07'


@python_2_unicode_compatible
class Group(UUIDModel):
    """
    This class represents a group, associated with one authenticator
    """
    # pylint: disable=model-missing-unicode
    manager = UnsavedForeignKey(Authenticator, on_delete=models.CASCADE, related_name='groups')
    name = models.CharField(max_length=128, db_index=True)
    state = models.CharField(max_length=1, default=State.ACTIVE, db_index=True)
    comments = models.CharField(max_length=256, default='')
    users = models.ManyToManyField(User, related_name='groups')
    is_meta = models.BooleanField(default=False, db_index=True)
    meta_if_any = models.BooleanField(default=False)
    groups = models.ManyToManyField('self', symmetrical=False)
    created = models.DateTimeField(default=getSqlDatetime, blank=True)

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare default order and unique multiple field index
        """
        unique_together = (("manager", "name"),)
        ordering = ('name',)
        app_label = 'uds'

    def getManager(self):
        """
        Returns the authenticator object that owns this user.

        :note: The returned value is an instance of the authenticator class used to manage this user, not a db record.
        """
        return self.manager.getInstance()

    def __str__(self):
        if self.is_meta:
            return "Meta group {0}(id:{1}) with groups {2}".format(self.name, self.id, list(self.groups.all()))
        else:
            return "Group {0}(id:{1}) from auth {2}".format(self.name, self.id, self.manager.name)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        In this case, this is a dummy method, waiting for something useful to do :-)

        :note: If destroy raises an exception, the deletion is not taken.
        """
        toDelete = kwargs['instance']
        # Todelete is a group

        # We invoke removeGroup. If this raises an exception, group will not
        # be removed
        toDelete.getManager().removeGroup(toDelete.name)

        # Clears related logs
        log.clearLogs(toDelete)

        logger.debug('Deleted group {0}'.format(toDelete))


signals.pre_delete.connect(Group.beforeDelete, sender=Group)
