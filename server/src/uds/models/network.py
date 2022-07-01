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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models

from uds.core.util import net

from .transport import Transport
from .authenticator import Authenticator
from .uuid_model import UUIDModel
from .tag import TaggingMixin


logger = logging.getLogger(__name__)


class Network(UUIDModel, TaggingMixin):  # type: ignore
    """
    This model is used for keeping information of networks associated with transports (right now, just transports..)
    """

    name = models.CharField(max_length=64, unique=True)
    net_start = models.BigIntegerField(db_index=True)
    net_end = models.BigIntegerField(db_index=True)
    net_string = models.CharField(max_length=128, default='')
    transports = models.ManyToManyField(
        Transport, related_name='networks', db_table='uds_net_trans'
    )
    authenticators = models.ManyToManyField(
        Authenticator, related_name='networks', db_table='uds_net_auths'
    )

    # "fake" declarations for type checking
    objects: 'models.manager.Manager[Network]'

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    @staticmethod
    def networksFor(ip: str) -> typing.Iterable['Network']:
        """
        Returns the networks that are valid for specified ip in dotted quad (xxx.xxx.xxx.xxx)
        """
        ipInt = net.ipToLong(ip)
        return Network.objects.filter(net_start__lte=ipInt, net_end__gte=ipInt)

    @staticmethod
    def create(name: str, netRange: str) -> 'Network':
        """
        Creates an network record, with the specified net start and net end (dotted quad)

        Args:
            netStart: Network start

            netEnd: Network end
        """
        nr = net.networkFromString(netRange)
        return Network.objects.create(
            name=name, net_start=nr[0], net_end=nr[1], net_string=netRange
        )

    @property
    def netStart(self) -> str:
        """
        Property to access the quad dotted format of the stored network start

        Returns:
            string representing the dotted quad of this network start
        """
        return net.longToIp(self.net_start)

    @property
    def netEnd(self) -> str:
        """
        Property to access the quad dotted format of the stored network end

        Returns:
            string representing the dotted quad of this network end
        """
        return net.longToIp(self.net_end)

    def ipInNetwork(self, ip: str) -> bool:
        """
        Returns true if the specified ip is in this network
        """
        return net.ipToLong(ip) >= self.net_start and net.ipToLong(ip) <= self.net_end

    def update(self, name: str, netRange: str):
        """
        Updated this network with provided values

        Args:
            name: new name of the network

            netStart: new Network start (quad dotted)

            netEnd: new Network end (quad dotted)
        """
        self.name = name
        nr = net.networkFromString(netRange)
        self.net_start = nr[0]
        self.net_end = nr[1]
        self.net_string = netRange
        self.save()

    def __str__(self) -> str:
        return u'Network {} ({}) from {} to {}'.format(
            self.name,
            self.net_string,
            net.longToIp(self.net_start),
            net.longToIp(self.net_end),
        )

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:
        from uds.core.util.permissions import clean

        toDelete = kwargs['instance']

        logger.debug('Before delete auth %s', toDelete)

        # Clears related permissions
        clean(toDelete)


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(Network.beforeDelete, sender=Network)
