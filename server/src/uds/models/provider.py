# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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

from django.db import models
from django.db.models import signals

from uds.core.util import log
from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.services import ServiceProvider
    from uds.models import Service

logger = logging.getLogger(__name__)


class Provider(ManagedObjectModel, TaggingMixin):
    """
    A Provider represents the Service provider itself, (i.e. a KVM Server or a Terminal Server)
    """

    maintenance_mode = models.BooleanField(default=False, db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Provider]'
    services: 'models.manager.RelatedManager[Service]'

    class Meta(ManagedObjectModel.Meta):  # pyright: ignore
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    def get_type(self) -> type['ServiceProvider']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object
        """
        from uds.core import services  # pylint: disable=import-outside-toplevel

        return services.factory().lookup(self.data_type) or services.ServiceProvider

    def get_instance(self, values: typing.Optional[dict[str, str]] = None) -> 'ServiceProvider':
        prov: 'ServiceProvider' = typing.cast('ServiceProvider', super().get_instance(values=values))
        return prov

    def is_in_maintenance(self) -> bool:
        return self.maintenance_mode

    @staticmethod
    def type_filter(type_: str) -> collections.abc.Iterable['Provider']:
        for i in Provider.objects.filter(data_type=type):
            yield i

    def __str__(self) -> str:
        return f'Provider {self.name} of type {self.data_type} (id:{self.id})'

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Provider class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        to_delete: 'Provider' = kwargs['instance']
        logger.debug('Before delete service provider %s', to_delete)

        # Only tries to get instance if data is not empty
        if to_delete.data != '':
            s = to_delete.get_instance()
            s.destroy()
            s.env.clean_related_data()

        # Clears related logs
        log.clear_logs(to_delete)

        # Clears related permissions
        clean(to_delete)


# : Connects a pre deletion signal to Provider
signals.pre_delete.connect(Provider.pre_delete, sender=Provider)
