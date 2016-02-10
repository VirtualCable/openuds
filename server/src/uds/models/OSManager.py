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

__updated__ = '2016-02-10'

from django.utils.encoding import python_2_unicode_compatible
from django.db import IntegrityError
from django.db.models import signals

from uds.models.ManagedObjectModel import ManagedObjectModel
from uds.models.Tag import TaggingMixin

import logging

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class OSManager(ManagedObjectModel, TaggingMixin):
    '''
    An OS Manager represents a manager for responding requests for agents inside services.
    '''
    # pylint: disable=model-missing-unicode

    class Meta(ManagedObjectModel.Meta):
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)
        app_label = 'uds'

    def getType(self):
        '''
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from ServiceProviderFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        '''
        # We only need to get info from this, not access specific data (class specific info)
        from uds.core import osmanagers
        return osmanagers.factory().lookup(self.data_type)

    def remove(self):
        '''
        Removes this OS Manager only if there is no associated deployed service using it.

        Returns:
            True if the object has been removed

            False if the object can't be removed because it is being used by some DeployedService

        Raises:
        '''
        if self.deployedServices.all().count() > 0:
            return False
        self.delete()
        return True

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
        toDelete = kwargs['instance']
        if toDelete.deployedServices.count() > 0:
            raise IntegrityError('Can\'t remove os managers with assigned deployed services')
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env().clearRelatedData()

        logger.debug('Before delete os manager {}'.format(toDelete))

# : Connects a pre deletion signal to OS Manager
signals.pre_delete.connect(OSManager.beforeDelete, sender=OSManager)
