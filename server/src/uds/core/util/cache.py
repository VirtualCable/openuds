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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import codecs
import pickle  # nosec: This is e controled pickle loading
import typing
import logging


from django.db import transaction
from uds.models.cache import Cache as DBCache
from uds.models.util import getSqlDatetime

from .hash import hash_key

logger = logging.getLogger(__name__)


class Cache:
    # Simple hits vs missses counters
    hits = 0
    misses = 0

    # Some aliases
    DEFAULT_VALIDITY = 60
    SHORT_VALIDITY = 5
    LONG_VALIDITY = 3600

    _owner: str
    _bowner: bytes

    def __init__(self, owner: typing.Union[str, bytes]):
        self._owner = owner.decode('utf-8') if isinstance(owner, bytes) else owner
        self._bowner = self._owner.encode('utf8')

    def __getKey(self, key: typing.Union[str, bytes]) -> str:
        if isinstance(key, str):
            key = key.encode('utf8')
        return hash_key(self._bowner + key)

    def get(
        self, skey: typing.Union[str, bytes], defValue: typing.Any = None
    ) -> typing.Any:
        now = getSqlDatetime()
        # logger.debug('Requesting key "%s" for cache "%s"', skey, self._owner)
        try:
            key = self.__getKey(skey)
            # logger.debug('Key: %s', key)
            c: DBCache = DBCache.objects.get(pk=key)  # @UndefinedVariable
            # If expired
            if now > c.created + datetime.timedelta(seconds=c.validity):
                return defValue

            try:
                # logger.debug('value: %s', c.value)
                val = pickle.loads(  # nosec: This is e controled pickle loading
                    typing.cast(bytes, codecs.decode(c.value.encode(), 'base64'))
                )
            except Exception:  # If invalid, simple do no tuse it
                logger.exception('Invalid pickle from cache. Removing it.')
                c.delete()
                return defValue

            Cache.hits += 1
            return val
        except DBCache.DoesNotExist:  # @UndefinedVariable
            Cache.misses += 1
            # logger.debug('key not found: %s', skey)
            return defValue
        except Exception:
            Cache.misses += 1
            # logger.debug('Cache inaccesible: %s:%s', skey, e)
            return defValue

    def __getitem__(self, key: typing.Union[str, bytes]) -> typing.Any:
        """
        Returns the cached value for the given key using the [] operator
        """
        return self.get(key)

    def remove(self, skey: typing.Union[str, bytes]) -> bool:
        """
        Removes an stored cached item
        If cached item does not exists, nothing happens (no exception thrown)
        """
        # logger.debug('Removing key "%s" for uService "%s"' % (skey, self._owner))
        try:
            key = self.__getKey(skey)
            DBCache.objects.get(pk=key).delete()  # @UndefinedVariable
            return True
        except DBCache.DoesNotExist:  # @UndefinedVariable
            logger.debug('key not found')
            return False

    def __delitem__(self, key: typing.Union[str, bytes]) -> None:
        """
        Removes an stored cached item using the [] operator
        """
        self.remove(key)

    def clear(self) -> None:
        Cache.delete(self._owner)

    def put(
        self,
        skey: typing.Union[str, bytes],
        value: typing.Any,
        validity: typing.Optional[int] = None,
    ) -> None:
        # logger.debug('Saving key "%s" for cache "%s"' % (skey, self._owner,))
        if validity is None:
            validity = Cache.DEFAULT_VALIDITY
        key = self.__getKey(skey)
        strValue: str = codecs.encode(pickle.dumps(value), 'base64').decode()
        now = getSqlDatetime()
        try:
            DBCache.objects.create(
                owner=self._owner,
                key=key,
                value=strValue,
                created=now,
                validity=validity,
            )  # @UndefinedVariable
        except Exception:
            try:
                # Already exists, modify it
                c: DBCache = DBCache.objects.get(pk=key)  # @UndefinedVariable
                c.owner = self._owner
                c.key = key
                c.value = strValue
                c.created = now
                c.validity = validity
                c.save()
            except transaction.TransactionManagementError:
                logger.debug('Transaction in course, cannot store value')

    def __setitem__(self, key: typing.Union[str, bytes], value: typing.Any) -> None:
        """
        Stores a value in the cache using the [] operator with default validity
        """
        self.put(key, value)

    def refresh(self, skey: typing.Union[str, bytes]) -> None:
        # logger.debug('Refreshing key "%s" for cache "%s"' % (skey, self._owner,))
        try:
            key = self.__getKey(skey)
            c = DBCache.objects.get(pk=key)  # @UndefinedVariable
            c.created = getSqlDatetime()
            c.save()
        except DBCache.DoesNotExist:  # @UndefinedVariable
            logger.debug('Can\'t refresh cache key %s because it doesn\'t exists', skey)
            return

    @staticmethod
    def purge() -> None:
        DBCache.objects.all().delete()  # @UndefinedVariable

    @staticmethod
    def cleanUp() -> None:
        DBCache.cleanUp()  # @UndefinedVariable

    @staticmethod
    def delete(owner: typing.Optional[str] = None) -> None:
        # logger.info("Deleting cache items")
        if owner is None:
            objects = DBCache.objects.all()  # @UndefinedVariable
        else:
            objects = DBCache.objects.filter(owner=owner)  # @UndefinedVariable
        objects.delete()
