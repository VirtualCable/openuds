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

from uds.core.managers import publicationManager
from uds.core.util.state import State
from uds.core.environment import Environment
from uds.core.util import log

from .service_pool import ServicePool
from ..core.util.model import getSqlDatetime
from .uuid_model import UUIDModel


if typing.TYPE_CHECKING:
    from uds.core import services
    from uds.models import UserService

logger = logging.getLogger(__name__)


class ServicePoolPublicationChangelog(models.Model):
    # This should be "servicePool"
    publication: 'models.ForeignKey[ServicePool]' = models.ForeignKey(
        ServicePool, on_delete=models.CASCADE, related_name='changelog'
    )
    stamp = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)
    log = models.TextField(default='')

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[ServicePoolPublicationChangelog]'

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order and unique multiple field index
        """

        db_table = 'uds__deployed_service_pub_cl'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'Changelog for publication {self.publication.name}, rev {self.revision}: {self.log}'


class ServicePoolPublication(UUIDModel):
    """
    A deployed service publication keep track of data needed by services that needs "preparation". (i.e. Virtual machine --> base machine --> children of base machines)
    """

    deployed_service: 'models.ForeignKey[ServicePool]' = models.ForeignKey(
        ServicePool, on_delete=models.CASCADE, related_name='publications'
    )
    publish_date = models.DateTimeField(db_index=True)
    # data_type = models.CharField(max_length=128) # The data type is specified by the service itself
    data = models.TextField(default='')
    # Preparation state. The preparation of a service is a task that runs over time, we need to:
    #   * Prepare it
    #   * Use it
    #   * Remove it
    #   * Mark as failed
    # The responsible class will notify when we have to change state, and a deployed service will only be usable id it has at least
    # a prepared service "Usable" or it doesn't need to prepare anything (needsDeployment = False)
    state = models.CharField(max_length=1, default=State.PREPARING, db_index=True)
    state_date = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["ServicePoolPublication"]'
    userServices: 'models.manager.RelatedManager[UserService]'

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order and unique multiple field index
        """

        db_table = 'uds__deployed_service_pub'
        ordering = ('publish_date',)
        app_label = 'uds'

    def getEnvironment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents
        """
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)  # type: ignore

    def getInstance(self) -> 'services.Publication':
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
        if not self.deployed_service.service:
            raise Exception('No service assigned to publication')
        serviceInstance = self.deployed_service.service.getInstance()
        osManager = self.deployed_service.osmanager
        osManagerInstance = osManager.getInstance() if osManager else None

        # Sanity check, so it's easier to find when we have created
        # a service that needs publication but do not have

        if serviceInstance.publicationType is None:
            raise Exception(
                f'Class {serviceInstance.__class__.__name__} do not have defined publicationType but needs to be published!!!'
            )

        publication = serviceInstance.publicationType(
            self.getEnvironment(),
            service=serviceInstance,
            osManager=osManagerInstance,
            revision=self.revision,
            dsName=self.deployed_service.name,
            uuid=self.uuid,
            dbPublication=self,
        )
        # Only invokes deserialization if data has something. '' is nothing
        if self.data:
            publication.deserialize(self.data)
        return publication

    def updateData(self, publication):
        """
        Updates the data field with the serialized uds.core.services.Publication

        Args:
            dsp: uds.core.services.Publication to serialize

        :note: This method do not saves the updated record, just updates the field
        """
        self.data = publication.serialize()
        self.save(update_fields=['data'])

    def setState(self, state: str) -> None:
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        self.state_date = getSqlDatetime()
        self.state = state
        self.save(update_fields=['state_date', 'state'])

    def unpublish(self) -> None:
        """
        Tries to remove the publication

        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        """

        publicationManager().unpublish(self)

    def cancel(self):
        """
        Invoques the cancelation of this publication
        """

        publicationManager().cancel(self)

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        toDelete: ServicePoolPublication = kwargs['instance']
        toDelete.getEnvironment().clearRelatedData()

        # Delete method is invoked directly by PublicationManager,
        # Destroying a publication is not obligatory an 1 step action.
        # It's handled as "publish", and as so, it can be a multi-step process

        # Clears related logs
        log.clearLogs(toDelete)

        logger.debug('Deleted publication %s', toDelete)

    def __str__(self) -> str:
        return f'Publication {self.deployed_service.name}, rev {self.revision}, state {State.toString(self.state)}'


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(
    ServicePoolPublication.beforeDelete, sender=ServicePoolPublication
)
