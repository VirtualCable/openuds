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

__updated__ = '2016-02-26'

from django.db import models
from django.db.models import signals
from django.utils.encoding import python_2_unicode_compatible

from uds.core.util import net

from uds.models.ManagedObjectModel import ManagedObjectModel
from uds.models.Tag import TaggingMixin

import logging

logger = logging.getLogger(__name__)


@python_2_unicode_compatible
class Transport(ManagedObjectModel, TaggingMixin):
    '''
    A Transport represents a way of connecting the user with the service.

    Sample of transports are RDP, Spice, Web file uploader, etc...
    '''
    # pylint: disable=model-missing-unicode
    priority = models.IntegerField(default=0, db_index=True)
    nets_positive = models.BooleanField(default=False)

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
        from uds.core import transports

        return transports.factory().lookup(self.data_type)

    def validForIp(self, ip):
        '''
        Checks if this transport is valid for the specified IP.

        Args:
           ip: Numeric ip address to check validity for. (xxx.xxx.xxx.xxx).

        Returns:
            True if the ip can access this Transport.

            False if the ip can't access this Transport.

            The ip check is done this way:
            * If The associated network is empty, the result is always True
            * If the associated network is not empty, and nets_positive (field) is True, the result will be True if
            the ip is contained in any subnet associated with this transport.
            * If the associated network is empty, and nets_positive (field) is False, the result will be True if
            the ip is NOT contained in ANY subnet associated with this transport.

        Raises:

        :note: Ip addresses has been only tested with IPv4 addresses
        '''
        if self.networks.count() == 0:
            return True
        ip = net.ipToLong(ip)
        if self.nets_positive:
            return self.networks.filter(net_start__lte=ip, net_end__gte=ip).count() > 0
        else:
            return self.networks.filter(net_start__lte=ip, net_end__gte=ip).count() == 0

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

        logger.debug('Before delete transport {}'.format(toDelete))
        # Only tries to get instance if data is not empty
        if toDelete.data != '':
            s = toDelete.getInstance()
            s.destroy()
            s.env.clearRelatedData()

        # Clears related permissions
        clean(toDelete)

# : Connects a pre deletion signal to OS Manager
signals.pre_delete.connect(Transport.beforeDelete, sender=Transport)
