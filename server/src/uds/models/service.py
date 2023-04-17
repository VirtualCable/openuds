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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models

from uds.core.environment import Environment
from uds.core.util import log
from uds.core.util import unique
from uds.core.util import net

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin
from .provider import Provider

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models.service_pool import ServicePool
    from uds.core import services


logger = logging.getLogger(__name__)


class ServiceTokenAlias(models.Model):
    """
    This model stores the alias for a service token.
    """

    service = models.ForeignKey(
        'Service', on_delete=models.CASCADE, related_name='aliases'
    )
    alias = models.CharField(max_length=64, unique=True)

    def __str__(self)  -> str:
        return str(self.alias)  # pylint complains about CharField

# pylint: disable=no-member
class Service(ManagedObjectModel, TaggingMixin):  # type: ignore
    """
    A Service represents an specidied type of service offered to final users,
    with it configuration (i.e. a KVM Base Machine for cloning or a Terminal
    Server configuration).
    """

    provider: 'models.ForeignKey[Provider]' = models.ForeignKey(
        Provider, related_name='services', on_delete=models.CASCADE
    )

    token = models.CharField(
        max_length=64, default=None, null=True, blank=True, unique=True
    )

    # 0 -> Standard max count type, that is, count only "creating and running" instances
    # 1 -> Count all instances, including "waint for delete" and "deleting" ones
    max_services_count_type = models.PositiveIntegerField(default=0)

    _cachedInstance: typing.Optional['services.Service'] = None

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["Service"]'
    deployedServices: 'models.manager.RelatedManager[ServicePool]'
    aliases: 'models.manager.RelatedManager[ServiceTokenAlias]'

    class Meta(ManagedObjectModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order and unique multiple field index
        """

        ordering = ('name',)
        app_label = 'uds'
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'name'], name='u_srv_provider_name'
            )
        ]

    def getEnvironment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.getEnvForTableElement(
            self._meta.verbose_name,  # type: ignore
            self.id,
            {
                'mac': unique.UniqueMacGenerator,
                'name': unique.UniqueNameGenerator,
                'id': unique.UniqueGIDGenerator,
            },
        )

    def getInstance(
        self, values: typing.Optional[typing.Dict[str, str]] = None
    ) -> 'services.Service':
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
        if self._cachedInstance and values is None:
            # logger.debug('Got cached instance instead of deserializing a new one for {}'.format(self.name))
            return self._cachedInstance

        prov: 'services.ServiceProvider' = self.provider.getInstance()
        sType = prov.getServiceByType(self.data_type)

        if sType:
            obj = sType(self.getEnvironment(), prov, values, uuid=self.uuid)
            self.deserialize(obj, values)
        else:
            raise Exception(
                f'Service type of {self.data_type} is not recogniced by provider {prov.name}'
            )

        self._cachedInstance = obj

        return obj

    def getType(self) -> typing.Type['services.Service']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        """
        from uds.core import services  # pylint: disable=import-outside-toplevel,redefined-outer-name

        prov: typing.Type['services.ServiceProvider'] = self.provider.getType()
        return prov.getServiceByType(self.data_type) or services.Service

    def isInMaintenance(self) -> bool:
        # orphaned services?
        return self.provider.isInMaintenance() if self.provider else True

    def testServer(
        self, host: str, port: typing.Union[str, int], timeout: float = 4
    ) -> bool:
        return net.testConnection(host, port, timeout)

    @property
    def oldMaxAccountingMethod(self) -> bool:
        # Compatibility with old accounting method
        # Counts only "creating and running" instances for max limit checking
        return self.max_services_count_type == 0

    @property
    def newMaxAccountingMethod(self) -> bool:
        # Compatibility with new accounting method,
        # Counts EVERYTHING for max limit checking
        return self.max_services_count_type == 1

    def __str__(self) -> str:
        return f'{self.name} of type {self.data_type} (id:{self.id})'

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        toDelete = kwargs['instance']

        logger.debug('Before delete service %s', toDelete)
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env.clearRelatedData()

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)


# : Connects a pre deletion signal to Service
models.signals.pre_delete.connect(Service.beforeDelete, sender=Service)
