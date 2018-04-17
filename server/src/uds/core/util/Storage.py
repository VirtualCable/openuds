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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.db import transaction
from uds.models.Storage import Storage as dbStorage
from uds.core.util import encoders
import hashlib
import logging
import pickle
import six

logger = logging.getLogger(__name__)


class Storage(object):

    def __init__(self, owner):
        self._owner = owner.encode('utf-8') if isinstance(owner, six.text_type) else owner

    def __getKey(self, key):
        h = hashlib.md5()
        h.update(self._owner)
        h.update(key.encode('utf8') if isinstance(key, six.text_type) else key)
        return h.hexdigest()

    def saveData(self, skey, data, attr1=None):
        key = self.__getKey(skey)
        if isinstance(data, six.text_type):
            data = data.encode('utf-8')
        data = encoders.encode(data, 'base64', asText=True)
        attr1 = '' if attr1 is None else attr1
        try:
            dbStorage.objects.create(owner=self._owner, key=key, data=data, attr1=attr1)  # @UndefinedVariable
        except Exception:
            dbStorage.objects.filter(key=key).update(owner=self._owner, data=data, attr1=attr1)  # @UndefinedVariable
        # logger.debug('Key saved')

    def put(self, skey, data):
        return self.saveData(skey, data)

    def putPickle(self, skey, data, attr1=None):
        return self.saveData(skey, pickle.dumps(data, protocol=2), attr1)  # Protocol 2 is compatible with python 2.7. This will be unnecesary when fully migrated

    def updateData(self, skey, data, attr1=None):
        self.saveData(skey, data, attr1)

    def readData(self, skey, fromPickle=False):
        try:
            key = self.__getKey(skey)
            logger.debug('Accesing to {0} {1}'.format(skey, key))
            c = dbStorage.objects.get(pk=key)  # @UndefinedVariable
            val = encoders.decode(c.data, 'base64')

            if fromPickle:
                return val

            try:
                return val.decode('utf-8')  # Tries to encode in utf-8
            except:
                return val
        except dbStorage.DoesNotExist:  # @UndefinedVariable
            logger.debug('key not found')
            return None

    def get(self, skey):
        return self.readData(skey)

    def getPickle(self, skey):
        v = self.readData(skey, True)
        if v is not None:
            v = pickle.loads(v)
        return v

    def getPickleByAttr1(self, attr1):
        try:
            return pickle.loads(encoders.decode(dbStorage.objects.filter(owner=self._owner, attr1=attr1)[0].data, 'base64'))  # @UndefinedVariable
        except Exception:
            return None

    def remove(self, skey):
        try:
            key = self.__getKey(skey)
            dbStorage.objects.filter(key=key).delete()  # @UndefinedVariable
        except Exception:
            pass

    def lock(self):
        """
        Use with care. If locked, it must be unlocked before returning
        """
        dbStorage.objects.lock()  # @UndefinedVariable

    def unlock(self):
        """
        Must be used to unlock table
        """
        dbStorage.objects.unlock()  # @UndefinedVariable

    def locateByAttr1(self, attr1):
        if isinstance(attr1, (list, tuple)):
            query = dbStorage.objects.filter(owner=self._owner, attr1_in=attr1)  # @UndefinedVariable
        else:
            query = dbStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable

        for v in query:
            yield encoders.decode(v.data, 'base64')

    def filter(self, attr1):
        if attr1 is None:
            query = dbStorage.objects.filter(owner=self._owner)  # @UndefinedVariable
        else:
            query = dbStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable

        for v in query:  # @UndefinedVariable
            yield (v.key, encoders.decode(v.data, 'base64'), v.attr1)

    def filterPickle(self, attr1=None):
        for v in self.filter(attr1):
            yield (v[0], pickle.loads(v[1]), v[2])

    @staticmethod
    def delete(owner=None):
        if owner is None:
            objects = dbStorage.objects.all()  # @UndefinedVariable
        else:
            objects = dbStorage.objects.filter(owner=owner)  # @UndefinedVariable
        objects.delete()
