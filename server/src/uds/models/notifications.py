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
from enum import IntEnum
import logging
import typing

from django.db import models, transaction
from django.utils.translation import gettext as _


from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.messaging import Notifier as NotificationProviderModule

class NotificationLevel(IntEnum):
    """
    Notification Levels
    """
    INFO = 0
    WARNING = 1
    ERROR = 2
    CRITICAL = 3

    # Return all notification levels as tuples of (level value, level name)
    @classmethod
    def all(cls):
        return [(level.value, level.name) for level in (cls.INFO, cls.WARNING, cls.ERROR, cls.CRITICAL)]
    

# This model will be available on local "persistent" storage and also on configured database
class Notification(models.Model):
    stamp = models.DateTimeField(auto_now_add=True)
    group = models.CharField(max_length=128, db_index=True)
    identificator = models.CharField(max_length=128, db_index=True)
    level = models.PositiveSmallIntegerField()
    message = models.TextField()
    # Processed is only used on local persistent storage
    # On local storage will be set to "True" if notification has been procesed, but not transferred to remote DB
    # As soon as it is stored on DB, the record on local storage will be deleted
    # For remote storage, this field will be set to True when the notification is processed
    processed = models.BooleanField(default=False)

    # "fake" declarations for type checking
    objects: 'models.BaseManager[Notification]'

    class Meta:
        """
        Meta class to declare db table
        """

        db_table = 'uds_notification'
        app_label = 'uds'

    @staticmethod
    def getPersistentQuerySet() -> 'models.QuerySet[Notification]':
        return Notification.objects.using('persistent')

    @staticmethod
    def savePersistent(record: 'Notification') -> None:
        record.save(using='persistent')

    @staticmethod
    def deletePersistent(record: 'Notification') -> None:
        record.delete(using='persistent')

    @staticmethod
    def atomicPersistent() -> 'transaction.Atomic':
        return transaction.atomic(using='persistent')


class Notifier(ManagedObjectModel, TaggingMixin):
    name = models.CharField(max_length=128, default='')
    comments = models.CharField(max_length=256, default='')
    enabled = models.BooleanField(default=True)
    level = models.PositiveSmallIntegerField(default=NotificationLevel.ERROR)

    # "fake" declarations for type checking
    objects: 'models.manager.Manager[Notifier]'

    class Meta:
        """
        Meta class to declare db table
        """

        db_table = 'uds_notify_prov'
        app_label = 'uds'

    def getType(self) -> typing.Type['NotificationProviderModule']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object
        """
        from uds.core import messaging  # pylint: disable=redefined-outer-name

        kind_ = messaging.factory().lookup(self.data_type) 
        if kind_ is None:
            raise Exception('Notifier type not found: {0}'.format(self.data_type))
        return kind_

    def getInstance(
        self, values: typing.Optional[typing.Dict[str, str]] = None
    ) -> 'NotificationProviderModule':
        return typing.cast('NotificationProviderModule', super().getInstance(values=values))


