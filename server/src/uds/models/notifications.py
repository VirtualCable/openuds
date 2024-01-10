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
import logging
import typing
import collections.abc

from django.db import models, transaction

from uds.core.util.log import LogLevel

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.core.messaging import Notifier as NotificationProviderModule


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
    # objects: 'models.BaseManager[Notification]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_notification'
        app_label = 'uds'

    @staticmethod
    def get_persistent_queryset() -> 'models.QuerySet[Notification]':
        return Notification.objects.using('persistent')

    def save_persistent(self) -> None:
        self.save(using='persistent')

    def delete_persistent(self) -> None:
        self.delete(using='persistent')

    @staticmethod
    def atomic_persistent() -> 'transaction.Atomic':
        return transaction.atomic(using='persistent')


class Notifier(ManagedObjectModel, TaggingMixin):
    name = models.CharField(max_length=128, default='')
    comments = models.CharField(max_length=256, default='')
    enabled = models.BooleanField(default=True)
    level = models.PositiveSmallIntegerField(default=LogLevel.ERROR)

    # "fake" declarations for type checking
    objects: 'models.manager.Manager[Notifier]'

    class Meta:  # pylint: disable=too-few-public-methods
        """
        Meta class to declare db table
        """

        db_table = 'uds_notify_prov'
        app_label = 'uds'

    def get_type(self) -> type['NotificationProviderModule']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object
        """
        from uds.core import messaging  # pylint: disable=import-outside-toplevel

        kind = messaging.factory().lookup(self.data_type)
        if kind is None:
            raise Exception(f'Notifier type not found: {self.data_type}')
        return kind

    def get_instance(
        self, values: typing.Optional[dict[str, str]] = None
    ) -> 'NotificationProviderModule':
        return typing.cast(
            'NotificationProviderModule', super().get_instance(values=values)
        )

    @staticmethod
    def pre_delete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        to_delete: 'Notifier' = kwargs['instance']
        # Only tries to get instance if data is not empty
        if to_delete.data:
            try:
                s = to_delete.get_instance()
                s.destroy()  # Invokes the destruction of "related own data"
                s.env.clearRelatedData()  # Clears related data, such as storage, cache, etc...
            except Exception as e:
                logger.error(
                    'Error processing deletion of notifier %s: %s (forced deletion)',
                    to_delete.name,
                    e,
                )

        logger.debug('Before delete notification provider %s', to_delete)


# : Connects a pre deletion signal to OS Manager
models.signals.pre_delete.connect(Notifier.pre_delete, sender=Notifier)
