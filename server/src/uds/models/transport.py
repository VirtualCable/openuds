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

from uds.core import transports

from uds.core.util import net

from .managed_object_model import ManagedObjectModel
from .tag import TaggingMixin

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import Network, ServicePool
    from uds.core.util.os_detector import KnownOS


logger = logging.getLogger(__name__)


class Transport(ManagedObjectModel, TaggingMixin):
    """
    A Transport represents a way of connecting the user with the service.

    Sample of transports are RDP, Spice, Web file uploader, etc...
    """
    # Constants for net_filter
    NO_FILTERING = 'n'
    ALLOW = 'a'
    DENY = 'd'

    # pylint: disable=model-missing-unicode
    priority = models.IntegerField(default=0, db_index=True)
    net_filtering = models.CharField(max_length=1, default=NO_FILTERING, db_index=True)
    # We store allowed oss as a comma-separated list
    allowed_oss = models.CharField(max_length=255, default='')
    # Label, to group transports on meta pools
    label = models.CharField(max_length=32, default='', db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Transport]'

    deployedServices: 'models.manager.RelatedManager[ServicePool]'
    networks: 'models.manager.RelatedManager[Network]'

    class Meta(ManagedObjectModel.Meta):
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    def getInstance(
        self, values: typing.Optional[typing.Dict[str, str]] = None
    ) -> 'transports.Transport':
        return typing.cast('transports.Transport', super().getInstance(values=values))

    def getType(self) -> typing.Type['transports.Transport']:
        """
        Get the type of the object this record represents.

        The type is Python type, it obtains this type from TransportsFactory and associated record field.

        Returns:
            The python type for this record object

        :note: We only need to get info from this, not access specific data (class specific info)
        """
        return transports.factory().lookup(self.data_type) or transports.Transport

    def validForIp(self, ipStr: str) -> bool:
        """
        Checks if this transport is valid for the specified IP.

        Args:
           ip: Numeric ip address to check validity for. (xxx.xxx.xxx.xxx).

        Returns:
            True if the ip can access this Transport.

            False if the ip can't access this Transport.

            The check is done using the net_filtering field.
            if net_filtering is 'x' (disabled), then the result is always True
            if net_filtering is 'a' (allow), then the result is True is the ip is in the networks
            if net_filtering is 'd' (deny), then the result is True is the ip is not in the networks
        Raises:

        :note: Ip addresses has been only tested with IPv4 addresses
        """
        if self.net_filtering == Transport.NO_FILTERING:
            return True
        ip, version = net.ipToLong(ipStr)
        # Allow
        if self.net_filtering == Transport.ALLOW:
            return self.networks.filter(net_start__lte=ip, net_end__gte=ip, version=version).exists()
        # Deny, must not be in any network
        return self.networks.filter(net_start__lte=ip, net_end__gte=ip).exists() is False

    def validForOs(self, os: 'KnownOS') -> bool:
        """If this transport is configured to be valid for the specified OS.

        Args:
            os (KnownOS): OS to check

        Returns:
            bool: True if this transport is valid for the specified OS, False otherwise
        """
        return not self.allowed_oss or os.name in self.allowed_oss.split(',')

    def __str__(self) -> str:
        return '{} of type {} (id:{})'.format(self.name, self.data_type, self.id)

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean

        toDelete = kwargs['instance']

        logger.debug('Before delete transport %s', toDelete)
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env.clearRelatedData()

        # Clears related permissions
        clean(toDelete)


# : Connects a pre deletion signal to OS Manager
models.signals.pre_delete.connect(Transport.beforeDelete, sender=Transport)
