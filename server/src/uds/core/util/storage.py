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
import logging
import pickle
import typing
import base64
import hashlib
from collections.abc import MutableMapping

from django.db import transaction
from uds.models.storage import Storage as DBStorage
from uds.core.util import encoders

logger = logging.getLogger(__name__)

def _calcKey(owner: bytes, key: bytes, extra: typing.Optional[bytes] = None) -> str:
    h = hashlib.md5()
    h.update(owner)
    h.update(key)
    if extra:
        h.update(extra)
    return h.hexdigest()

def _encodeValue(key: str, value: typing.Any) -> str:
    return base64.b64encode(pickle.dumps((key, value))).decode()

def _decodeValue(dbk: str, value: typing.Optional[str]) -> typing.Tuple[str, typing.Any]:
    if value:
        try:
            v = pickle.loads(base64.b64decode(value.encode()))
            if isinstance(v, tuple):
                return typing.cast(typing.Tuple[str, typing.Any], v)
            # Fix value so it contains also the "key" (in this case, no valid key...)
            return ('#' + dbk, v)
        except Exception as e:
            logger.warn('Unknown pickable value: %s (%s)', value, e)
    return ('', None)


class StorageAsDict(MutableMapping):
    '''
    Accesses storage as dictionary. Much more convenient that old method
    '''
    def __init__(self, owner: str, group: typing.Optional[str], atomic: bool = False) -> None:
        self._group = group or ''
        self._owner = owner
        self._atomic = atomic  # Not used right now, maybe removed

    def _key(self, key: str) -> str:
        if key[0] == '#':
            # Compat with old dbk
            return key[1:]
        return _calcKey(self._owner.encode(), key.encode(), self._group.encode())

    def __getitem__(self, key: str) -> typing.Any:
        if not isinstance(key, str):
            raise TypeError('Key must be str, {} found'.format(type(key)))

        dbk = self._key(key)
        logger.debug('Getitem: %s', dbk)
        try:
            c: DBStorage = DBStorage.objects.get(pk=dbk)
            return _decodeValue(dbk, c.data)[1]  # Ignores original key
        except DBStorage.DoesNotExist:
            return None

    def __setitem__(self, key: str, value: typing.Any) -> None:
        if not isinstance(key, str):
            raise TypeError('Key must be str type, {} found'.format(type(key)))

        dbk = self._key(key)
        logger.debug('Setitem: %s = %s', dbk, value)
        data = _encodeValue(key, value)
        c, created = DBStorage.objects.update_or_create(key=dbk, defaults={'data': data, 'attr1': self._group, 'owner': self._owner})

    def __delitem__(self, key: str):
        dbk = self._key(key)
        logger.debug('Delitem: %s', key)
        DBStorage.objects.filter(key=dbk).delete()

    def __iter__(self):
        '''
        Iterates through keys
        '''
        return iter((_decodeValue(i.key, i.data)[0] for i in DBStorage.objects.filter(owner=self._owner, attr1=self._group)))

    def __contains__(self, key: object) -> bool:
        logger.debug('Contains: %s', key)
        if isinstance(key, str):
            dbk = self._key(key)
            return DBStorage.objects.filter(owner=self._owner, attr1=self._group, key=dbk).count() > 0
        return False

    def __len__(self):
        return DBStorage.objects.filter(owner=self._owner, attr1=self._group).count()


class StorageAccess:
    '''
    Allows the access to the storage as a dict, with atomic transaction if requested
    '''
    def __init__(self, owner: str, group: typing.Optional[str] = None, atomic: typing.Optional[bool] = False):
        self._owner = owner
        self._group = group
        self._atomic = transaction.atomic() if atomic else None

    def __enter__(self):
        if self._atomic:
            self._atomic.__enter__()
        return StorageAsDict(self._owner, self._group, bool(self._atomic))

    def __exit__(self, exc_type, exc_value, traceback):
        if self._atomic:
            self._atomic.__exit__(exc_type, exc_value, traceback)

class Storage:
    _owner: str
    _bownwer: bytes

    def __init__(self, owner: typing.Union[str, bytes]):
        self._owner = owner.decode('utf-8') if isinstance(owner, bytes) else owner
        self._bowner = self._owner.encode('utf8')

    def getKey(self, key: typing.Union[str, bytes]) -> str:
        return _calcKey(self._bowner, key.encode('utf8') if isinstance(key, str) else key)

    def saveData(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        # If None is to be saved, remove
        if not data:
            self.remove(skey)
            return

        key = self.getKey(skey)
        if isinstance(data, str):
            data = data.encode('utf-8')
        data = encoders.encodeAsStr(data, 'base64')
        attr1 = attr1 or ''
        try:
            DBStorage.objects.create(owner=self._owner, key=key, data=data, attr1=attr1)
        except Exception:
            with transaction.atomic():
                DBStorage.objects.filter(key=key).select_for_update().update(owner=self._owner, data=data, attr1=attr1)  # @UndefinedVariable
        # logger.debug('Key saved')

    def put(self, skey: typing.Union[str, bytes], data: typing.Any) -> None:
        return self.saveData(skey, data)

    def putPickle(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        return self.saveData(skey, pickle.dumps(data), attr1)  # Protocol 2 is compatible with python 2.7. This will be unnecesary when fully migrated

    def updateData(self, skey: typing.Union[str, bytes], data: typing.Any, attr1: typing.Optional[str] = None) -> None:
        self.saveData(skey, data, attr1)

    def readData(self, skey: typing.Union[str, bytes], fromPickle: bool = False) -> typing.Optional[typing.Union[str, bytes]]:
        try:
            key = self.getKey(skey)
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

    def remove(self, skey: typing.Union[typing.Iterable[typing.Union[str, bytes]], str, bytes]) -> None:
        keys: typing.Iterable[typing.Union[str, bytes]] = [skey] if isinstance(skey, (str, bytes)) else skey
        try:
            # Process several keys at once
            DBStorage.objects.filter(key__in=[self.getKey(k) for k in keys]).delete()
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

    def map(self, group: typing.Optional[str] = None, atomic: typing.Optional[bool] = False):
        return StorageAccess(self._owner, group, atomic)

    def locateByAttr1(self, attr1: typing.Union[typing.Iterable[str], str]) -> typing.Iterable[bytes]:
        if isinstance(attr1, str):
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1__in=attr1)  # @UndefinedVariable

        for v in query:
            yield typing.cast(bytes, encoders.decode(v.data, 'base64'))

    def filter(self, attr1: typing.Optional[str] = None, forUpdate: bool = False) -> typing.Iterable[typing.Tuple[str, bytes, str]]:
        if attr1 is None:
            query = DBStorage.objects.filter(owner=self._owner)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable

        if forUpdate:
            query = query.select_for_update()

        for v in query:  # @UndefinedVariable
            yield (v.key, typing.cast(bytes, encoders.decode(v.data, 'base64')), v.attr1)

    def filterPickle(self, attr1: typing.Optional[str] = None, forUpdate: bool = False) -> typing.Iterable[typing.Tuple[str, typing.Any, str]]:
        for v in self.filter(attr1, forUpdate):
            yield (v[0], pickle.loads(v[1]), v[2])

    @staticmethod
    def delete(owner: str) -> None:
        DBStorage.objects.filter(owner=owner).delete()
