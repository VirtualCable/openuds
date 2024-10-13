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
import logging
import time
import typing

from django.db import transaction, OperationalError, connection
from django.db.utils import IntegrityError
from uds.core import consts

from uds.models.unique_id import UniqueId
from uds.core.util.model import sql_stamp_seconds

if typing.TYPE_CHECKING:
    from django.db import models

logger = logging.getLogger(__name__)


class UniqueGenerator:
    __slots__ = ('_owner', '_basename')

    # owner is the owner of the UniqueID
    _owner: str
    # base name for filtering unique ids. (I.e. "mac", "ip", "ipv6" ....)
    _basename: str

    def __init__(self, owner: str, basename: typing.Optional[str] = None) -> None:
        self._owner = owner
        self._basename = basename or 'uds'

    def set_basename(self, basename: str) -> None:
        self._basename = basename

    def _range_filter(
        self, range_start: int, range_end: int = consts.system.MAX_SEQ, for_update: bool = False
    ) -> 'models.QuerySet[UniqueId]':
        # Order is defined on UniqueId model, and is '-seq' by default (so this gets items in sequence order)
        # if not for update, do not use the clause :)
        objects = UniqueId.objects.select_for_update() if for_update else UniqueId.objects
        return objects.filter(basename=self._basename, seq__gte=range_start, seq__lte=range_end)

    def _get(self, range_start: int = 0, range_end: typing.Optional[int] = None) -> int:
        """
        Tries to generate a new unique id in the range provided. This unique id
        is global to "unique ids' database
        """
        # First look for a name in the range defined
        # So we allow 0 to be a valid range end
        range_end = range_end or consts.system.MAX_SEQ
        stamp = sql_stamp_seconds()
        seq = range_start
        # logger.debug(UniqueId)
        counter = 0
        while True:
            counter += 1
            try:
                # logger.debug('Creating new seq in range {}-{}'.format(rangeStart, rangeEnd))
                with transaction.atomic():
                    range_filter = self._range_filter(range_start, range_end, for_update=True)
                    item: typing.Optional[UniqueId] = None
                    try:
                        item = range_filter.filter(assigned=False).order_by('seq')[0]
                        item.owner = self._owner
                        item.assigned = True
                        item.stamp = stamp
                        item.save(update_fields=['owner', 'assigned', 'stamp'])

                        seq = item.seq
                        break
                    except IndexError:  # No free element found
                        item = None

                    # No item was found on first instance (already created, but freed)
                    # No free "reuseable" found, so we will create a new one
                    try:
                        last = range_filter.filter(assigned=True).order_by('-seq')[0]
                        seq = last.seq + 1
                    except IndexError:
                        # If there is no assigned at database, so first one
                        seq = range_start

                    if seq > range_end:
                        return -1  # No ids free in range

                    # May ocurr on some circustance that a concurrency access gives same item twice, in this case, we
                    # will get an "duplicate key error",
                    UniqueId.objects.create(
                        owner=self._owner,
                        basename=self._basename,
                        seq=seq,
                        assigned=True,
                        stamp=stamp,
                    ) 
                    break
            except OperationalError:  # Locked, may ocurr for example on sqlite. We will wait a bit
                # logger.exception('Got database locked')
                if counter % 5 == 0:
                    connection.close()
                time.sleep(1)
            except IntegrityError:  
                # Concurrent creation, may fail, simply retry
                pass
            except Exception:
                logger.exception('Error')
                return -1
        return seq

    def _transfer(self, seq: int, to_generator: 'UniqueGenerator') -> bool:
        self._range_filter(0, for_update=True).filter(owner=self._owner, seq=seq).update(
            owner=to_generator._owner,
            basename=to_generator._basename,
            stamp=sql_stamp_seconds(),
        )
        return True

    def _free(self, seq: int) -> None:
        logger.debug('Freeing seq %s from %s (%s)', seq, self._owner, self._basename)
        with transaction.atomic():
            flt = (
                self._range_filter(0, for_update=True)
                .filter(owner=self._owner, seq=seq)
                .update(owner='', assigned=False, stamp=sql_stamp_seconds())
            )
        if flt > 0:
            self._purge()

    def _purge(self) -> None:
        logger.debug('Purging UniqueID database')
        try:
            last: UniqueId = self._range_filter(0, for_update=False).filter(assigned=True)[0]
            logger.debug('Last: %s', last)
            seq = last.seq + 1
        except Exception:
            # logger.exception('Error here')
            seq = 0
        with transaction.atomic():
            self._range_filter(seq).delete()  # Clean ups all unassigned after last assigned in this range

    def release(self) -> None:
        UniqueId.objects.select_for_update().filter(owner=self._owner).update(
            assigned=False, owner='', stamp=sql_stamp_seconds()
        )
        self._purge()

    def release_older_than(self, stamp: typing.Optional[int] = None) -> None:
        stamp = sql_stamp_seconds() if stamp is None else stamp
        UniqueId.objects.select_for_update().filter(owner=self._owner, stamp__lt=stamp).update(
            assigned=False, owner='', stamp=stamp
        )
        self._purge()


class UniqueIDGenerator(UniqueGenerator):
    """
    Unique ID generator
    """

    def get(self, range_start: int = 0, range_end: int = consts.system.MAX_SEQ) -> int:
        return self._get(range_start, range_end)

    def transfer(self, seq: int, target_id_generator: 'UniqueIDGenerator') -> bool:
        return self._transfer(seq, target_id_generator)

    def free(self, seq: int) -> None:
        self._free(seq)
