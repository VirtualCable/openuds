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

from uds.core.util import net

from .uuid_model import UUIDModel
from .tag import TaggingMixin


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from .transport import Transport
    from .authenticator import Authenticator
    

class Network(UUIDModel, TaggingMixin):
    """
    This model is used for keeping information of networks associated with transports (right now, just transports..)
    """

    name = models.CharField(max_length=64, unique=True)

    start = models.CharField(
        max_length=32, default='0', db_index=True
    )  # 128 bits, for IPv6, network byte order, hex
    end = models.CharField(
        max_length=32, default='0', db_index=True
    )  # 128 bits, for IPv6, network byte order, hex

    version = models.IntegerField(default=4)  # network type, ipv4 or ipv6
    net_string = models.CharField(max_length=240, default='')
    transports: 'models.ManyToManyField[Transport, Network]' = models.ManyToManyField(
        'Transport', related_name='networks', db_table='uds_net_trans'
    )
    authenticators: 'models.ManyToManyField[Authenticator, Network]' = models.ManyToManyField(
        'Authenticator', related_name='networks', db_table='uds_net_auths'
    )

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Network]'

    class Meta(UUIDModel.Meta):  # pyright: ignore
        """
        Meta class to declare default order
        """

        ordering = ('name',)
        app_label = 'uds'

    @staticmethod
    def hexlify(number: int) -> str:
        """
        Converts a number to hex, but with 32 chars, and with leading zeros
        """
        # return f'{number:032x}'
        return hex(number)[2:].zfill(32)

    @staticmethod
    def unhexlify(number: str) -> int:
        """
        Converts a hex string to a number
        """
        return int(number, 16)

    @staticmethod
    def get_networks_for_ip(ip: str) -> collections.abc.Iterable['Network']:
        """
        Returns the networks that are valid for specified ip in dotted quad (xxx.xxx.xxx.xxx)
        """
        ip_int, version = net.ip_to_long(ip)
        hex_value = Network.hexlify(ip_int)
        # hexlify is used to convert to hex, and then decode to convert to string
        return Network.objects.filter(
            version=version,
            start__lte=hex_value,
            end__gte=hex_value,
        )

    @staticmethod
    def create(name: str, net_range: str) -> 'Network':
        """
        Creates an network record, with the specified network range. Supports IPv4 and IPv6
        IPV4 has a versatile format, that can be:
            - A single IP
            - A range of IPs, in the form of "startIP - endIP"
            - A network, in the form of "network/mask"
            - A network, in the form of "network netmask mask"
            - A network, in the form of "network*'

        Args:
            name: Name of the network
            net_range: Network range in any supported format

        """
        nr = net.network_from_str(net_range)
        return Network.objects.create(
            name=name,
            start=Network.hexlify(nr.start),
            end=Network.hexlify(nr.end),
            net_string=net_range,
            version=nr.version,
        )

    @property
    def net_start(self) -> int:
        """
        Returns the network start as an integer
        """
        return Network.unhexlify(self.start)

    @net_start.setter
    def net_start(self, value: int) -> None:
        """
        Sets the network start
        """
        self.start = Network.hexlify(value)

    @property
    def net_end(self) -> int:
        """
        Returns the network end as an integer
        """
        return Network.unhexlify(self.end)

    @net_end.setter
    def net_end(self, value: int) -> None:
        """
        Sets the network end
        """
        self.end = Network.hexlify(value)

    @property
    def str_net_start(self) -> str:
        """
        Property to access the quad dotted format of the stored network start

        Returns:
            string representing the dotted quad of this network start
        """
        return net.long_to_ip(self.net_start)

    @property
    def str_net_end(self) -> str:
        """
        Property to access the quad dotted format of the stored network end

        Returns:
            string representing the dotted quad of this network end
        """
        return net.long_to_ip(self.net_end)

    def contains(self, ip: str) -> bool:
        """
        Returns True if the specified ip is in this network
        """
        # if net_string is '*', then we are in all networks, return true
        if self.net_string == '*':
            return True
        ip_int, version = net.ip_to_long(ip)
        return self.version == version and self.net_start <= ip_int <= self.net_end

    # utility method to allow "in" operator
    __contains__ = contains

    def save(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        """
        Overrides save to update the start, end and version fields
        """
        rng = net.network_from_str(self.net_string)
        self.start = Network.hexlify(rng.start)
        self.end = Network.hexlify(rng.end)
        self.version = rng.version
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'Network {self.name} ({self.net_string}) from {self.str_net_start} to {self.str_net_end} ({self.version})'

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        to_delete: 'Network' = kwargs['instance']

        logger.debug('Before delete auth %s', to_delete)

        # Clears related permissions
        clean(to_delete)


# Connects a pre deletion signal to Authenticator
models.signals.pre_delete.connect(Network.pre_delete, sender=Network)
