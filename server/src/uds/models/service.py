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

from django.db import models

from uds.core.environment import Environment
from uds.core.util import log
from uds.core.util import net
from uds.core.types.services import ServicesCountingType

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin
from .provider import Provider

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models.service_pool import ServicePool
    from uds.models.user_service import UserService
    from uds.core import services, types


logger = logging.getLogger(__name__)


class ServiceTokenAlias(models.Model):
    """
    This model stores the alias for a service token.
    """

    service: 'models.ForeignKey[Service]' = models.ForeignKey(
        'Service', on_delete=models.CASCADE, related_name='aliases'
    )
    alias = models.CharField(max_length=64, unique=True)
    unique_id = models.CharField(
        max_length=128, default='', db_index=True
    )  # Used to locate an already created alias for a userService and service

    def __str__(self) -> str:
        return str(self.alias)


# pylint: disable=no-member
class Service(ManagedObjectModel, TaggingMixin):
    """
    A Service represents an specidied type of service offered to final users,
    with it configuration (i.e. a KVM Base Machine for cloning or a Terminal
    Server configuration).
    """

    provider = models.ForeignKey(Provider, related_name='services', on_delete=models.CASCADE)

    token = models.CharField(max_length=64, default=None, null=True, blank=True, unique=True)

    max_services_count_type = models.PositiveIntegerField(default=ServicesCountingType.STANDARD)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Service"]'
    deployedServices: 'models.manager.RelatedManager[ServicePool]'
    aliases: 'models.manager.RelatedManager[ServiceTokenAlias]'

    class Meta(ManagedObjectModel.Meta):  # pyright: ignore
        """
        Meta class to declare default order and unique multiple field index
        """

        ordering = ('name',)
        app_label = 'uds'
        constraints = [models.UniqueConstraint(fields=['provider', 'name'], name='u_srv_provider_name')]

    def get_environment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.environment_for_table_record(
            self._meta.verbose_name or self._meta.db_table,
            self.id,
        )

    def get_instance(self, values: typing.Optional[dict[str, str]] = None) -> 'services.Service':
        """
        Instantiates the object this record contains.

        Every single record of Provider model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.

        Returns:
            The instance Instance of the class this provider represents

        Raises:
        """
        if self._cached_instance and values is None:
            # logger.debug('Got cached instance instead of deserializing a new one for {}'.format(self.name))
            return typing.cast('services.Service', self._cached_instance)

        prov: 'services.ServiceProvider' = self.provider.get_instance()
        service_type = prov.get_service_by_type(self.data_type)

        if service_type:
            obj = service_type(self.get_environment(), prov, values, uuid=self.uuid)
            self.deserialize(obj, values)
        else:
            raise Exception(f'Service type of {self.data_type} is not recognized by provider {prov.mod_name}')

        self._cached_instance = obj

        return obj

    def get_type(self) -> type['services.Service']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        """
        from uds.core import services  # pylint: disable=import-outside-toplevel,redefined-outer-name

        prov: type['services.ServiceProvider'] = self.provider.get_type()
        return prov.get_service_by_type(self.data_type) or services.Service

    @property
    def services_counting_type(self) -> ServicesCountingType:
        return ServicesCountingType.from_int(self.max_services_count_type)

    def is_in_maintenance(self) -> bool:
        # orphaned services?
        return self.provider.is_in_maintenance() if self.provider else True

    def test_connectivity(self, host: str, port: typing.Union[str, int], timeout: float = 4) -> bool:
        return net.test_connectivity(host, int(port), timeout)

    def notify_preconnect(self, userService: 'UserService', info: 'types.connections.ConnectionData') -> None:
        """
        Notify preconnect event to service, so it can do whatever it needs to do before connecting

        Args:
            userService: User service that is going to be connected
            info: Connection data

        Note:
            Override this method if you need to do something before connecting to a service
            (i.e. invoke notify_preconnect using a Server, or whatever you need to do)
        """
        logger.warning('No actor notification available for user service %s', userService.friendly_name)

    @property
    def old_max_accounting_method(self) -> bool:
        # Compatibility with old accounting method
        # Counts only "creating and running" instances for max limit checking
        return self.services_counting_type == ServicesCountingType.STANDARD

    @property
    def new_max_accounting_method(self) -> bool:
        # Compatibility with new accounting method,
        # Counts EVERYTHING for max limit checking
        return self.services_counting_type == ServicesCountingType.CONSERVATIVE

    def __str__(self) -> str:
        return f'{self.name} of type {self.data_type} (id:{self.id})'

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        to_delete: 'Service' = kwargs['instance']

        logger.debug('Before delete service %s', to_delete)
        # Only tries to get instance if data is not empty
        if to_delete.data != '':
            s = to_delete.get_instance()
            s.destroy()
            s.env.clean_related_data()

        # Clears related logs
        log.clear_logs(to_delete)

        # Clears related permissions
        clean(to_delete)


# : Connects a pre deletion signal to Service
models.signals.pre_delete.connect(Service.pre_delete, sender=Service)
