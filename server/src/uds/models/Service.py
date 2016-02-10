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

from uds.core.Environment import Environment
from uds.core.util import log
from uds.core.util import unique
from uds.models.ManagedObjectModel import ManagedObjectModel
from uds.models.Tag import TaggingMixin

from uds.models.Provider import Provider

import logging


__updated__ = '2016-02-10'


logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Service(ManagedObjectModel, TaggingMixin):
    '''
    A Service represents an specidied type of service offered to final users, with it configuration (i.e. a KVM Base Machine for cloning
    or a Terminal Server configuration).
    '''
    # pylint: disable=model-missing-unicode
    provider = models.ForeignKey(Provider, related_name='services')

    class Meta(ManagedObjectModel.Meta):
        '''
        Meta class to declare default order and unique multiple field index
        '''
        ordering = ('name',)
        unique_together = (("provider", "name"),)
        app_label = 'uds'

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        # from uds.core.util.UniqueMacGenerator import UniqueMacGenerator
        # from uds.core.util.UniqueNameGenerator import UniqueNameGenerator

        return Environment.getEnvForTableElement(
            self._meta.verbose_name,
            self.id,
            {
                'mac': unique.UniqueMacGenerator,
                'name': unique.UniqueNameGenerator,
                'id': unique.UniqueGIDGenerator,
            }
        )

    def getInstance(self, values=None):
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
        prov = self.provider.getInstance()
        sType = prov.getServiceByType(self.data_type)
        env = self.getEnvironment()
        s = sType(env, prov, values)
        self.deserialize(s, values)
        return s

    def getType(self):
        '''
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        return self.provider.getType().getServiceByType(self.data_type)

    def isInMaintenance(self):
        return self.provider is not None and self.provider.isInMaintenance()

    def __str__(self):
        return u"{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)

    @staticmethod
    def beforeDelete(sender, **kwargs):
        '''
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        '''
        from uds.core.util.permissions import clean
        toDelete = kwargs['instance']

        logger.debug('Before delete service {}'.format(toDelete))
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

# : Connects a pre deletion signal to Service
signals.pre_delete.connect(Service.beforeDelete, sender=Service)
