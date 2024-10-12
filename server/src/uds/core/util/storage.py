# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
import contextlib
import pickle  # nosec: This is e controled pickle use
import base64
import hashlib
import codecs
import pickletools
import typing
import collections.abc
import logging

from django.db import transaction, models
from uds.models.storage import Storage as DBStorage

logger = logging.getLogger(__name__)

MARK = '_mgb_'


def _old_calculate_key(owner: bytes, key: bytes) -> str:
    h = hashlib.md5(usedforsecurity=False)
    h.update(owner)
    h.update(key)
    return h.hexdigest()


def _calculate_key(owner: bytes, key: bytes) -> str:
    h = hashlib.sha256(usedforsecurity=False)
    h.update(owner)
    h.update(key)
    return h.hexdigest()


def _encode_value(key: str, value: typing.Any) -> str:
    return base64.b64encode(pickle.dumps((MARK, key, value))).decode()


def _decode_value(dbk: str, value: typing.Optional[str]) -> tuple[str, typing.Any]:
    if value:
        try:
            v = pickle.loads(base64.b64decode(value.encode()))  # nosec: This is e controled pickle loading
            if isinstance(v, tuple) and v[0] == MARK:
                return typing.cast(tuple[str, typing.Any], v[1:])
            # Fix value so it contains also the "key" (in this case, the original key is lost, we have only the hash value...)
            return ('#' + dbk, typing.cast(typing.Any, v))
        except Exception:
            try:
                return ('#' + dbk, base64.b64decode(value.encode()).decode())
            except Exception as e:
                logger.warning('Unknown decodeable value: %s (%s)', value, e)
    return ('', None)


class StorageAsDict(dict[str, typing.Any]):
    """
    Accesses storage as dictionary. Much more convenient that old method
    """

    _group: str
    _owner: str
    _atomic: bool

    def __init__(
        self,
        owner: str,
        group: typing.Optional[str],
        atomic: bool = False,
    ) -> None:
        """Initializes an storage as dict accesor

        Args:
            owner (str): owner of the storage
            group (typing.Optional[str]): group for this dict
            atomic (bool, optional): if True, operations with DB will be atomic
            compat (bool, optional): if True, keys will be SAVED with old format
                                     (that is, without the key) so it can be read by old api
        """
        self._group = group or ''
        self._owner = owner
        self._atomic = atomic  # Not used right now, maybe removed

    @property
    def _db(self) -> typing.Union[models.QuerySet[DBStorage], models.Manager[DBStorage]]:
        if self._atomic:
            # TODO: add skip_locked ASAP (mariadb 10.6+)
            return DBStorage.objects.select_for_update()

        return DBStorage.objects

    @property
    def _filtered(self) -> 'models.QuerySet[DBStorage]':
        fltr_params = {'owner': self._owner}
        if self._group:
            fltr_params['attr1'] = self._group
        return typing.cast('models.QuerySet[DBStorage]', self._db.filter(**fltr_params))

    def _key(self, key: str, old_method: bool = False) -> str:
        if key[0] == '#':
            # Compat with old db key
            return key[1:]
        if not old_method:
            return _calculate_key(self._owner.encode(), key.encode())
        return _old_calculate_key(self._owner.encode(), key.encode())

    def __getitem__(self, key: str) -> typing.Any:
        if not isinstance(key, str):  # pyright: ignore reportUnnecessaryIsInstance
            raise TypeError(f'Key must be str, {type(key)} found')

        # First, try new key, and, if needed, old key
        # If old key is found, it will be updated to new key
        for use_old_method in (False, True):
            db_key = self._key(key, old_method=use_old_method)
            try:
                c: DBStorage = self._db.get(pk=db_key)
                if c.owner != self._owner:  # Maybe a key collision,
                    logger.error('Key collision detected for key %s', key)
                    return None
                _, value = _decode_value(db_key, c.data)
                if use_old_method:
                    # Update key on db
                    c.delete()
                    DBStorage.objects.create(key=self._key(key), owner=self._owner, data=c.data, attr1=c.attr1)
                return value
            except DBStorage.DoesNotExist:
                pass
        return None

    def __setitem__(self, key: str, value: typing.Any) -> None:
        if not isinstance(key, str):  # pyright: ignore reportUnnecessaryIsInstance
            raise TypeError(f'Key must be str type, {type(key)} found')

        dbk = self._key(key)
        data = _encode_value(key, value)
        # ignores return value, we don't care if it was created or updated
        DBStorage.objects.update_or_create(
            key=dbk, defaults={'data': data, 'attr1': self._group, 'owner': self._owner}
        )

    def __delitem__(self, key: str) -> None:
        dbk = self._key(key)
        DBStorage.objects.filter(key=dbk).delete()

    def __iter__(self) -> typing.Iterator[str]:
        """
        Iterates through keys
        """
        return iter(_decode_value(i.key, i.data)[0] for i in self._filtered)

    def __contains__(self, key: object) -> bool:
        if isinstance(key, str):
            return self._filtered.filter(key=self._key(key)).exists()
        return False

    def __len__(self) -> int:
        return self._filtered.count()

    # Optimized methods, avoid re-reading from DB
    def items(self) -> typing.Iterator[tuple[str, typing.Any]]:  # type: ignore   # compatible type
        return iter(_decode_value(i.key, i.data) for i in self._filtered)

    def keys(self) -> typing.Iterator[str]:  # type: ignore   # compatible type
        return iter(_decode_value(i.key, i.data)[0] for i in self._filtered)

    def values(self) -> typing.Iterator[typing.Any]:  # type: ignore   # compatible type
        return iter(_decode_value(i.key, i.data)[1] for i in self._filtered)

    def get(self, key: str, default: typing.Any = None) -> typing.Any:
        return self[key] or default

    def delete(self, key: str) -> None:
        self.__delitem__(key)  # pylint: disable=unnecessary-dunder-call

    def clear(self) -> None:
        self._filtered.delete()  # Removes all keys

    # Custom utility methods
    @property
    def group(self) -> str:
        return self._group or ''

    @group.setter
    def group(self, value: str) -> None:
        self._group = value or ''


class Storage:
    _owner: str
    _bownwer: bytes

    def __init__(self, owner: typing.Union[str, bytes]):
        if isinstance(owner, bytes):
            self._owner = owner.decode('utf-8')
            self._bowner = owner
        elif isinstance(
            owner, str
        ):  # pyright: ignore reportUnnecessaryIsInstance  Wants to ensure that it is a string no runtime error
            self._owner = owner
            self._bowner = owner.encode('utf8')
        else:
            raise TypeError(f'Owner must be str or bytes, {type(owner)} found')

    def get_key(self, key: typing.Union[str, bytes], old_method: bool = False) -> str:
        bkey: bytes = key.encode('utf8') if isinstance(key, str) else key
        if not old_method:
            return _calculate_key(self._bowner, bkey)
        return _old_calculate_key(self._bowner, bkey)

    def save_to_db(
        self,
        skey: typing.Union[str, bytes],
        data: typing.Any,
        attr1: typing.Optional[str] = None,
    ) -> None:
        # If None is to be saved, remove
        if not data:
            self.remove(skey)
            return

        key = self.get_key(skey)
        if isinstance(data, str):
            data = data.encode('utf-8')
        data_encoded = base64.b64encode(data).decode()
        attr1 = attr1 or ''
        try:
            DBStorage.objects.create(owner=self._owner, key=key, data=data_encoded, attr1=attr1)
        except Exception:
            with transaction.atomic():
                DBStorage.objects.filter(key=key).select_for_update().update(
                    owner=self._owner, data=data_encoded, attr1=attr1
                )  # @UndefinedVariable

    def put(self, skey: typing.Union[str, bytes], data: typing.Any) -> None:
        return self.save_to_db(skey, data)

    def save_pickled(
        self,
        skey: typing.Union[str, bytes],
        data: typing.Any,
        attr1: typing.Optional[str] = None,
    ) -> None:
        return self.save_to_db(
            skey,
            pickletools.optimize(
                pickle.dumps(
                    data,
                    protocol=-1,
                )
            ),
            attr1,
        )

    def update_to_db(
        self,
        skey: typing.Union[str, bytes],
        data: typing.Any,
        attr1: typing.Optional[str] = None,
    ) -> None:
        self.save_to_db(skey, data, attr1)

    def read_from_db(
        self, skey: typing.Union[str, bytes], from_pickle: bool = False
    ) -> typing.Optional[typing.Union[str, bytes]]:
        for use_old_method in (False, True):
            try:
                key = self.get_key(skey, old_method=use_old_method)
                c: DBStorage = DBStorage.objects.get(pk=key)  # @UndefinedVariable
                val = base64.b64decode(c.data.encode())
                # if old key is used, update it to new key
                if use_old_method:
                    # Remove and re-create with new key
                    c.delete()
                    DBStorage.objects.create(
                        key=self.get_key(skey), owner=self._owner, data=c.data, attr1=c.attr1
                    )

                if from_pickle:
                    return val

                try:
                    return val.decode('utf-8')  # Tries to encode in utf-8
                except Exception:
                    return val
            except DBStorage.DoesNotExist:
                pass
        return None

    def read(self, skey: typing.Union[str, bytes]) -> typing.Optional[typing.Union[str, bytes]]:
        return self.read_from_db(skey)

    def read_string(self, skey: typing.Union[str, bytes]) -> typing.Optional[str]:
        data = self.read(skey)
        if isinstance(data, bytes):
            return data.decode('utf-8')
        return data

    def read_bytes(self, skey: typing.Union[str, bytes]) -> typing.Optional[bytes]:
        data = self.read(skey)
        if isinstance(data, str):
            return data.encode('utf-8')
        return data

    def read_pickled(self, skey: typing.Union[str, bytes]) -> typing.Any:
        v = self.read_from_db(skey, True)
        if v:
            return pickle.loads(typing.cast(bytes, v))  # nosec: This is e controled pickle loading
        return None

    def read_pickle_by_attr1(self, attr1: str, for_update: bool = False) -> typing.Any:
        try:
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)
            if for_update:
                query = query.select_for_update()
            return pickle.loads(  # nosec: This is e controled pickle loading
                codecs.decode(query[0].data.encode(), 'base64')
            )  # @UndefinedVariable
        except Exception:
            return None

    def remove(
        self, skey: typing.Union[collections.abc.Iterable[typing.Union[str, bytes]], str, bytes]
    ) -> None:
        keys: 'collections.abc.Iterable[str|bytes]'
        if isinstance(skey, (str, bytes)):
            keys = [skey]
        else:
            keys = skey  # typing.cast('collections.abc.Iterable[str|bytes]', skey)

        try:
            # Process several keys at once
            DBStorage.objects.filter(key__in=[self.get_key(k) for k in keys]).delete()
        except Exception:  # nosec: Not interested in processing exceptions, just ignores it
            pass

    @contextlib.contextmanager
    def as_dict(
        self,
        group: typing.Optional[str] = None,
        atomic: bool = False,
    ) -> typing.Iterator[StorageAsDict]:
        if atomic:
            with transaction.atomic():
                yield StorageAsDict(self._owner, group=group, atomic=True)
        else:
            yield StorageAsDict(self._owner, group=group, atomic=False)

    def search_by_attr1(
        self, attr1: typing.Union[collections.abc.Iterable[str], str]
    ) -> collections.abc.Iterable[bytes]:
        if isinstance(attr1, str):
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1__in=attr1)  # @UndefinedVariable

        for v in query:
            yield codecs.decode(v.data.encode(), 'base64')

    def filter(
        self, attr1: typing.Optional[str] = None, for_update: bool = False
    ) -> collections.abc.Iterable[tuple[str, bytes, 'str|None']]:
        if attr1 is None:
            query = DBStorage.objects.filter(owner=self._owner)  # @UndefinedVariable
        else:
            query = DBStorage.objects.filter(owner=self._owner, attr1=attr1)  # @UndefinedVariable

        if for_update:
            query = query.select_for_update()

        for v in query:  # @UndefinedVariable
            yield (v.key, codecs.decode(v.data.encode(), 'base64'), v.attr1)

    def filter_unpickle_by_attr(
        self, attr1: typing.Optional[str] = None, for_update: bool = False
    ) -> collections.abc.Iterable[tuple[str, typing.Any, 'str|None']]:
        for v in self.filter(attr1, for_update):
            yield (v[0], pickle.loads(v[1]), v[2])  # nosec: secure pickle load

    def clear(self) -> None:
        Storage.delete(self._owner)

    @staticmethod
    def delete(owner: str) -> None:
        DBStorage.objects.filter(owner=owner).delete()
