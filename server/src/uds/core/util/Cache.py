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
from datetime import datetime, timedelta
import typing

from django.db import transaction
import uds.models.cache
from uds.models.Util import getSqlDatetime
from uds.core.util import encoders

logger = logging.getLogger(__name__)


class Cache:
    # Simple hits vs missses counters
    hits = 0
    misses = 0

    DEFAULT_VALIDITY = 60

    _owner: str
    _bowner: bytes

    def __init__(self, owner: typing.Union[str, bytes]):
        self._owner = owner.decode('utf-8') if isinstance(owner, bytes) else owner
        self._bowner = self._owner.encode('utf8')

    def __getKey(self, key: typing.Union[str, bytes]) -> str:
        h = hashlib.md5()
        if isinstance(key, str):
            key = key.encode('utf8')
        h.update(self._bowner + key)
        return h.hexdigest()

    def get(self, skey: typing.Union[str, bytes], defValue: typing.Any = None) -> typing.Any:
        now: datetime = typing.cast(datetime, getSqlDatetime())
        logger.debug('Requesting key "%s" for cache "%s"', skey, self._owner)
        try:
            key = self.__getKey(skey)
            logger.debug('Key: %s', key)
            c: uds.models.cache = uds.models.cache.objects.get(pk=key)  # @UndefinedVariable
            # If expired
            if now > c.created + timedelta(seconds=c.validity):
                return defValue

            try:
                logger.debug('value: %s', c.value)
                val = pickle.loads(typing.cast(bytes, encoders.decode(c.value, 'base64')))
            except Exception:  # If invalid, simple do no tuse it
                logger.exception('Invalid pickle from cache. Removing it.')
                c.delete()
                return defValue

            Cache.hits += 1
            return val
        except uds.models.cache.DoesNotExist:  # @UndefinedVariable
            Cache.misses += 1
            logger.debug('key not found: %s', skey)
            return defValue
        except Exception as e:
            Cache.misses += 1
            logger.debug('Cache inaccesible: %s:%s', skey, e)
            return defValue

    def remove(self, skey: typing.Union[str, bytes]) -> bool:
        """
        Removes an stored cached item
        If cached item does not exists, nothing happens (no exception thrown)
        """
        # logger.debug('Removing key "%s" for uService "%s"' % (skey, self._owner))
        try:
            key = self.__getKey(skey)
            uds.models.cache.objects.get(pk=key).delete()  # @UndefinedVariable
            return True
        except uds.models.cache.DoesNotExist:  # @UndefinedVariable
            logger.debug('key not found')
            return False

    def clean(self) -> None:
        Cache.delete(self._owner)

    def put(self, skey: typing.Union[str, bytes], value: typing.Any, validity: typing.Optional[int] = None) -> None:
        # logger.debug('Saving key "%s" for cache "%s"' % (skey, self._owner,))
        if validity is None:
            validity = Cache.DEFAULT_VALIDITY
        key = self.__getKey(skey)
        value = typing.cast(str, encoders.encode(pickle.dumps(value), 'base64', asText=True))
        now: datetime = typing.cast(datetime, getSqlDatetime())
        try:
            uds.models.cache.objects.create(owner=self._owner, key=key, value=value, created=now, validity=validity)  # @UndefinedVariable
        except Exception:
            try:
                # Already exists, modify it
                c: uds.models.cache = uds.models.cache.objects.get(pk=key)  # @UndefinedVariable
                c.owner = self._owner
                c.key = key
                c.value = value
                c.created = now
                c.validity = validity
                c.save()
            except transaction.TransactionManagementError:
                logger.debug('Transaction in course, cannot store value')

    def refresh(self, skey: typing.Union[str, bytes]) -> None:
        # logger.debug('Refreshing key "%s" for cache "%s"' % (skey, self._owner,))
        try:
            key = self.__getKey(skey)
            c = uds.models.cache.objects.get(pk=key)  # @UndefinedVariable
            c.created = getSqlDatetime()
            c.save()
        except uds.models.cache.DoesNotExist:  # @UndefinedVariable
            logger.debug('Can\'t refresh cache key %s because it doesn\'t exists', skey)
            return

    @staticmethod
    def purge() -> None:
        uds.models.cache.objects.all().delete()  # @UndefinedVariable

    @staticmethod
    def cleanUp() -> None:
        uds.models.cache.cleanUp()  # @UndefinedVariable

    @staticmethod
    def delete(owner: typing.Optional[str] = None) -> None:
        # logger.info("Deleting cache items")
        if owner is None:
            objects = uds.models.cache.objects.all()  # @UndefinedVariable
        else:
            objects = uds.models.cache.objects.filter(owner=owner)  # @UndefinedVariable
        objects.delete()
