# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from django.db import IntegrityError, models

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import osmanagers
    from uds.models import ServicePool

logger = logging.getLogger(__name__)


class OSManager(ManagedObjectModel, TaggingMixin):
    """
    An OS Manager represents a manager for responding requests for agents inside services.
    """

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[OSManager]'
    deployedServices: 'models.manager.RelatedManager[ServicePool]'

    class Meta(ManagedObjectModel.Meta):
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    def getInstance(
        self, values: typing.Optional[typing.Dict[str, str]] = None
    ) -> 'osmanagers.OSManager':
        return typing.cast('osmanagers.OSManager', super().getInstance(values=values))

    def getType(self) -> typing.Type['osmanagers.OSManager']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this OsManagersFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        """
        # We only need to get info from this, not access specific data (class specific info)
        from uds.core import osmanagers

        return osmanagers.factory().lookup(self.data_type) or osmanagers.OSManager

    def remove(self) -> bool:
        """
        Removes this OS Manager only if there is no associated deployed service using it.

        Returns:
            True if the object has been removed

            False if the object can't be removed because it is being used by some ServicePool

        Raises:
        """
        if self.deployedServices.all().count() > 0:
            return False
        self.delete()
        return True

    def __str__(self) -> str:
        return "{0} of type {1} (id:{2})".format(self.name, self.data_type, self.id)

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        toDelete = kwargs['instance']
        if toDelete.deployedServices.count() > 0:
            raise IntegrityError(
                'Can\'t remove os managers with assigned deployed services'
            )
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env.clearRelatedData()

        logger.debug('Before delete os manager %s', toDelete)


# : Connects a pre deletion signal to OS Manager
models.signals.pre_delete.connect(OSManager.beforeDelete, sender=OSManager)
