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

__updated__ = '2014-04-24'

from django.db import models
from Transport import Transport
from uds.core.util import net

import logging

logger = logging.getLogger(__name__)


class Network(models.Model):
    '''
    This model is used for keeping information of networks associated with transports (right now, just transports..)
    '''
    name = models.CharField(max_length=64, unique=True)
    net_start = models.BigIntegerField(db_index=True)
    net_end = models.BigIntegerField(db_index=True)
    net_string = models.CharField(max_length=128, default='')
    transports = models.ManyToManyField(Transport, related_name='networks', db_table='uds_net_trans')

    class Meta:
        '''
        Meta class to declare default order
        '''
        ordering = ('name',)
        app_label = 'uds'


    @staticmethod
    def networksFor(ip):
        '''
        Returns the networks that are valid for specified ip in dotted quad (xxx.xxx.xxx.xxx)
        '''
        ip = net.ipToLong(ip)
        return Network.objects.filter(net_start__lte=ip, net_end__gte=ip)

    @staticmethod
    def create(name, netRange):
        '''
        Creates an network record, with the specified net start and net end (dotted quad)

        Args:
            netStart: Network start

            netEnd: Network end
        '''
        nr = net.networksFromString(netRange, False)
        return Network.objects.create(name=name, net_start=nr[0], net_end=nr[1], net_string=netRange)

    @property
    def netStart(self):
        '''
        Property to access the quad dotted format of the stored network start

        Returns:
            string representing the dotted quad of this network start
        '''
        return net.longToIp(self.net_start)

    @property
    def netEnd(self):
        '''
        Property to access the quad dotted format of the stored network end

        Returns:
            string representing the dotted quad of this network end
        '''
        return net.longToIp(self.net_end)

    def update(self, name, netRange):
        '''
        Updated this network with provided values

        Args:
            name: new name of the network

            netStart: new Network start (quad dotted)

            netEnd: new Network end (quad dotted)
        '''
        self.name = name
        nr = net.networksFromString(netRange, False)
        self.net_start = nr[0]
        self.net_end = nr[1]
        self.net_string = netRange
        self.save()

    def __unicode__(self):
        return u'Network {0} ({1}) from {2} to {3}'.format(self.name, self.net_string, net.longToIp(self.net_start), net.longToIp(self.net_end))
