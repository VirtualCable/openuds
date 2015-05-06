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
from uds.core.Environment import Environment
from uds.models.UUIDModel import UUIDModel

import logging

__updated__ = '2015-05-06'


logger = logging.getLogger(__name__)


class ManagedObjectModel(UUIDModel):
    '''
    Base abstract model for models that are top level Managed Objects
    (such as Authenticator, Transport, OSManager, Provider, Service ...)
    '''
    # pylint: disable=model-missing-unicode, abstract-class-not-used
    name = models.CharField(max_length=128, unique=False, db_index=True)
    data_type = models.CharField(max_length=128)
    data = models.TextField(default='')
    comments = models.CharField(max_length=256)

    class Meta(UUIDModel.Meta):
        '''
        Defines this is an abstract clas
        '''
        abstract = True

    def getEnvironment(self):
        '''
        Returns an environment valid for the record this object represents
        '''
        return Environment.getEnvForTableElement(self._meta.verbose_name, self.id)

    def deserialize(self, obj, values):
        '''
        Conditionally deserializes obj if not initialized via user interface and data holds something
        '''
        # Only unserializes if this is not initialized via user interface and
        # data contains something
        if values is None and self.data is not None and self.data != '':
            obj.unserialize(self.data)

    def getInstance(self, values=None):
        '''
        Instantiates the object this record contains.

        Every single record of Provider model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.

        Returns:
            The instance Instance of the class this provider represents
        Notes:
            Can be overriden
        '''
        klass = self.getType()
        env = self.getEnvironment()
        obj = klass(env, values)
        self.deserialize(obj, values)
        return obj

    def getType(self):
        '''
        Returns the type of self (as python type)
        Must be overriden!!!
        '''
        raise NotImplementedError('getType has not been implemented for {}'.format(self.__class__))

    def isOfType(self, type_):
        '''
        return True if self if of the requested type, else returns False
        '''
        return self.data_type == type_
