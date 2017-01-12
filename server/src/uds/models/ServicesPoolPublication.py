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

from uds.core.util.State import State
from uds.core.Environment import Environment
from uds.core.util import log

from uds.models.ServicesPool import DeployedService
from uds.models.Util import getSqlDatetime
from uds.models.UUIDModel import UUIDModel

import logging

__updated__ = '2017-01-12'


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class DeployedServicePublicationChangelog(models.Model):
    publication = models.ForeignKey(DeployedService, on_delete=models.CASCADE, related_name='changelog')
    stamp = models.DateTimeField()
    revision = models.PositiveIntegerField(default=1)
    log = models.TextField(default='')

    class Meta(UUIDModel.Meta):
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds__deployed_service_pub_cl'
        app_label = 'uds'

    def __str__(self):
        return 'Revision log  for publication {0}, rev {1}:  {2}'.format(self.publication.name, self.revision, self.log)


@python_2_unicode_compatible
class DeployedServicePublication(UUIDModel):
    '''
    A deployed service publication keep track of data needed by services that needs "preparation". (i.e. Virtual machine --> base machine --> children of base machines)
    '''
    # pylint: disable=model-missing-unicode
    deployed_service = models.ForeignKey(DeployedService, on_delete=models.CASCADE, related_name='publications')
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

    class Meta(UUIDModel.Meta):
        '''
        Meta class to declare default order and unique multiple field index
        '''
        db_table = 'uds__deployed_service_pub'
        ordering = ('publish_date',)
        app_label = 'uds'

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)

    def getInstance(self):
        '''
        Instantiates the object this record contains.

        Every single record of Provider model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.

        Returns:
            The instance Instance of the class this provider represents

        Raises:
        '''
        serviceInstance = self.deployed_service.service.getInstance()
        osManagerInstance = self.deployed_service.osmanager
        if osManagerInstance is not None:
            osManagerInstance = osManagerInstance.getInstance()
        # Sanity check, so it's easier to find when we have created
        # a service that needs publication but do not have

        if serviceInstance.publicationType is None:
            raise Exception('Tried to get a publication instance for a service that do not needs it')

        if serviceInstance.publicationType is None:
            raise Exception('Class {0} do not have defined publicationType but needs to be published!!!'.format(serviceInstance.__class__))

        dpl = serviceInstance.publicationType(self.getEnvironment(), service=serviceInstance, osManager=osManagerInstance, revision=self.revision, dsName=self.deployed_service.name, dbPublication=self)
        # Only invokes deserialization if data has something. '' is nothing
        if self.data != '' and self.data is not None:
            dpl.unserialize(self.data)
        return dpl

    def updateData(self, dsp):
        '''
        Updates the data field with the serialized uds.core.services.Publication

        Args:
            dsp: uds.core.services.Publication to serialize

        :note: This method do not saves the updated record, just updates the field
        '''
        self.data = dsp.serialize()

    def setState(self, state):
        '''
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        '''
        self.state_date = getSqlDatetime()
        self.state = state

    def unpublish(self):
        '''
        Tries to remove the publication

        No check is done, it simply redirects the request to PublicationManager, where checks are done.
        '''
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().unpublish(self)

    def cancel(self):
        '''
        Invoques the cancelation of this publication
        '''
        from uds.core.managers.PublicationManager import PublicationManager
        PublicationManager.manager().cancel(self)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        '''
        toDelete = kwargs['instance']
        toDelete.getEnvironment().clearRelatedData()

        # Delete method is invoked directly by PublicationManager,
        # Destroying a publication is not obligatory an 1 step action.
        # It's handled as "publish", and as so, it can be a multi-step process

        # Clears related logs
        log.clearLogs(toDelete)

        logger.debug('Deleted publication {0}'.format(toDelete))

    def __str__(self):
        return 'Publication {0}, rev {1}, state {2}'.format(self.deployed_service.name, self.revision, State.toString(self.state))

# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(DeployedServicePublication.beforeDelete, sender=DeployedServicePublication)

ServicePoolPublication = DeployedServicePublication

