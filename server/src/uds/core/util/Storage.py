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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import hashlib
import logging
import pickle
import typing

from django.db import transaction
from uds.models.Storage import Storage as DBStorage
from uds.core.util import encoders

logger = logging.getLogger(__name__)


class Storage:
    _owner: str
    _bownwer: bytes

    def __init__(self, owner: typing.Union[str, bytes]):
        self._owner = owner.decode('utf-8') if isinstance(owner, bytes) else owner
        self._bowner = self._owner.encode('utf8')

    def __getKey(self, key: typing.Union[str, bytes]) -> str:
        h = hashlib.md5()
        h.update(self._bowner)
        h.update(key.encode('utf8') if isinstance(key, str) else key)
        return h.hexdigest()

    def saveData(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        # If None is to be saved, remove
        if not data:
            self.remove(skey)
            return

        key = self.__getKey(skey)
        if isinstance(data, str):
            data = data.encode('utf-8')
        data = encoders.encode(data, 'base64', asText=True)
        attr1 = '' if attr1 is None else attr1
        try:
            DBStorage.objects.create(owner=self._owner, key=key, data=data, attr1=attr1)  # @UndefinedVariable
        except Exception:
            DBStorage.objects.filter(key=key).update(owner=self._owner, data=data, attr1=attr1)  # @UndefinedVariable
        # logger.debug('Key saved')

    def put(self, skey: typing.Union[str, bytes], data: typing.Any) -> None:
        return self.saveData(skey, data)

    def putPickle(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        return self.saveData(skey, pickle.dumps(data), attr1)  # Protocol 2 is compatible with python 2.7. This will be unnecesary when fully migrated

    def updateData(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        self.saveData(skey, data, attr1)

    def readData(self, skey: typing.Union[str, bytes], fromPickle: bool = False) -> typing.Optional[typing.Union[str, bytes]]:
        try:
            key = self.__getKey(skey)
            logger.debug('Accesing to %s %s', skey, key)
            c: DBStorage = DBStorage.objects.get(pk=key)  # @UndefinedVariable
            val: bytes = typing.cast(bytes, encoders.decode(c.data, 'base64'))

            if fromPickle:
                return val

            try:
                return val.decode('utf-8')  # Tries to encode in utf-8
            except Exception:
                return val
        except DBStorage.DoesNotExist:  # @UndefinedVariable
            logger.debug('key not found')
            return None

    def get(self, skey: typing.Union[str, bytes]) -> typing.Optional[typing.Union[str, bytes]]:
        return self.readData(skey)

    def getPickle(self, skey: typing.Union[str, bytes]) -> typing.Any:
        v = self.readData(skey, True)
        if v:
            return pickle.loads(typing.cast(bytes, v))
        return None

    def getPickleByAttr1(self, attr1: str, forUpdate: bool = False):
        try:
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)
            if forUpdate:
                query = query.select_for_update()
            return pickle.loads(typing.cast(bytes, encoders.decode(query[0].data, 'base64')))  # @UndefinedVariable
        except Exception:
            return None

    def remove(self, skey: typing.Union[str, bytes]) -> None:
        try:
            if isinstance(skey, (list, tuple)):
                # Process several keys at once
                DBStorage.objects.filter(key__in=[self.__getKey(k) for k in skey])
            else:
                key = self.__getKey(skey)
                DBStorage.objects.filter(key=key).delete()  # @UndefinedVariable
        except Exception:
            pass

    def lock(self):
        """
        Use with care. If locked, it must be unlocked before returning
        """
        # dbStorage.objects.lock()  # @UndefinedVariable

    def unlock(self):
        """
        Must be used to unlock table
        """
        # dbStorage.objects.unlock()  # @UndefinedVariable

    def locateByAttr1(self, attr1: typing.Union[typing.Iterable[str], str]) -> typing.Generator[bytes, None,None]:
        if isinstance(attr1, str):
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1_in=attr1)  # @UndefinedVariable

        for v in query:
            yield typing.cast(bytes, encoders.decode(v.data, 'base64'))

    def filter(self, attr1: typing.Optional[str], forUpdate: bool = False):
        if attr1 is None:
            query = DBStorage.objects.filter(owner=self._owner)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable

        if forUpdate:
            query = query.select_for_update()

        for v in query:  # @UndefinedVariable
            yield (v.key, encoders.decode(v.data, 'base64'), v.attr1)

    def filterPickle(self, attr1: typing.Optional[str] = None, forUpdate: bool = False):
        for v in self.filter(attr1, forUpdate):
            yield (v[0], pickle.loads(v[1]), v[2])

    @staticmethod
    def delete(owner: typing.Optional[str] = None):
        if owner is None:
            objects = DBStorage.objects.all()  # @UndefinedVariable
        else:
            objects = DBStorage.objects.filter(owner=owner)  # @UndefinedVariable
        objects.delete()
