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

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .authenticator import Authenticator
    from uds.core import mfas

logger = logging.getLogger(__name__)


class MFA(ManagedObjectModel, TaggingMixin):  # type: ignore
    """
    An OS Manager represents a manager for responding requests for agents inside services.
    """

    # Time to remember the device MFA in hours
    remember_device = models.IntegerField(default=0)
    # Limit of time for this MFA to be used, in seconds
    validity = models.IntegerField(default=0)

    # "fake" declarations for type checking
    # objects: 'models.BaseManager[MFA]'
    authenticators: 'models.manager.RelatedManager[Authenticator]'

    def get_instance(
        self, values: typing.Optional[dict[str, str]] = None
    ) -> 'mfas.MFA':
        return typing.cast('mfas.MFA', super().get_instance(values=values))

    def get_type(self) -> type['mfas.MFA']:
        """Get the type of the object this record represents.

        The type is a Python type, it obtains this MFA and associated record field.

        Returns:
            The python type for this record object

        Note:
            We only need to get info from this, not access specific data (class specific info)
        """
        # We only need to get info from this, not access specific data (class specific info)
        from uds.core import mfas  # pylint: disable=import-outside-toplevel

        return mfas.factory().lookup(self.data_type) or mfas.MFA

    def __str__(self) -> str:
        return f'MFA {self.name} of type {self.data_type} (id:{self.id})'

    @staticmethod
    def pre_delete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        to_delete: 'MFA' = kwargs['instance']
        # Only tries to get instance if data is not empty
        if to_delete.data:
            try:
                s = to_delete.get_instance()
                s.destroy()
                s.env.clearRelatedData()
            except Exception as e:
                logger.error(
                    'Error processing deletion of notifier %s: %s (forced deletion)',
                    to_delete.name,
                    e,
                )

        logger.debug('Before delete mfa provider %s', to_delete)


# : Connects a pre deletion signal to OS Manager
models.signals.pre_delete.connect(MFA.pre_delete, sender=MFA)
