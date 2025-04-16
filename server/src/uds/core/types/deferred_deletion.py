# -*- coding: utf-8 -*-

#
# Copyright (c) 2024 Virtual Cable S.L.U.
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
import collections.abc
import dataclasses
import datetime
import logging
import enum

from uds.core.consts import deferred_deletion as consts
from uds.core.types import deferred_deletion as types
from uds.core.util import storage
from uds.core.util.model import sql_now
from uds.models import Service
import typing

if typing.TYPE_CHECKING:
    from uds.core.services.generics.dynamic.service import DynamicService

logger = logging.getLogger(__name__)

class DeferredStorageGroup(enum.StrEnum):
    TO_STOP = 'to_stop'
    STOPPING = 'stopping'
    TO_DELETE = 'to_delete'
    DELETING = 'deleting'

    @staticmethod
    def from_str(value: str) -> 'DeferredStorageGroup':
        return DeferredStorageGroup(value)


@dataclasses.dataclass
class DeletionInfo:
    vmid: str
    created: datetime.datetime
    next_check: datetime.datetime
    service_uuid: str  # uuid of the service that owns this vmid (not the pool, but the service)
    fatal_retries: int = 0  # Fatal error retries
    total_retries: int = 0  # Total retries
    retries: int = 0  # Retries to stop again or to delete again in STOPPING_GROUP or DELETING_GROUP

    deferred_storage: typing.ClassVar[storage.Storage] = storage.Storage('deferdel_worker')

    @property
    def key(self) -> str:
        return DeletionInfo.generate_key(self.service_uuid, self.vmid)

    def sync_to_storage(self, group: types.DeferredStorageGroup) -> None:
        """
        Ensures that this object is stored on the storage
        If exists, it will be updated, if not, it will be created
        """
        with DeletionInfo.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            storage_dict[self.key] = self

    # For reporting
    def as_csv(self) -> str:
        return f'{self.vmid},{self.created},{self.next_check},{self.service_uuid},{self.fatal_retries},{self.total_retries},{self.retries}'

    @staticmethod
    def next_execution_calculator(*, fatal: bool = False, delay_rate: float = 1.0) -> datetime.datetime:
        """
        Returns the next check time for a deletion operation
        """
        return sql_now() + (
            consts.CHECK_INTERVAL * (consts.FATAL_ERROR_INTERVAL_MULTIPLIER if fatal else 1) * delay_rate
        )

    @staticmethod
    def generate_key(service_uuid: str, vmid: str) -> str:
        return f'{service_uuid}_{vmid}'

    @staticmethod
    def create_on_storage(group: str, vmid: str, service_uuid: str, delay_rate: float = 1.0) -> None:
        with DeletionInfo.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            storage_dict[DeletionInfo.generate_key(service_uuid, vmid)] = DeletionInfo(
                vmid=vmid,
                created=sql_now(),
                next_check=DeletionInfo.next_execution_calculator(delay_rate=delay_rate),
                service_uuid=service_uuid,
                # fatal, total an retries are 0 by default
            )

    @staticmethod
    def get_from_storage(
        group: types.DeferredStorageGroup,
    ) -> tuple[dict[str, 'DynamicService'], list['DeletionInfo']]:
        """
        Get a list of objects to be processed from storage

        Note:
            This method will remove the objects from storage, so if needed, has to be readded
            This is so we can release locks as soon as possible
        """
        count = 0
        infos: list[DeletionInfo] = []

        services: dict[str, 'DynamicService'] = {}

        # First, get ownership of to_delete objects to be processed
        # We do this way to release db locks as soon as possible
        now = sql_now()
        with DeletionInfo.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            for key, info in sorted(
                typing.cast(collections.abc.Iterable[tuple[str, DeletionInfo]], storage_dict.unlocked_items()),
                key=lambda x: x[1].next_check,
            ):
                # if max retries reached, remove it
                if info.total_retries >= consts.MAX_RETRAYABLE_ERROR_RETRIES:
                    logger.error(
                        'Too many retries deleting %s from service %s, removing from deferred deletion',
                        info.vmid,
                        info.service_uuid,
                    )
                    del storage_dict[key]
                    continue

                if info.next_check > now:  # If not time to process yet, skip
                    continue
                try:
                    if info.service_uuid not in services:
                        services[info.service_uuid] = typing.cast(
                            'DynamicService', Service.objects.get(uuid=info.service_uuid).get_instance()
                        )
                except Exception as e:
                    logger.error('Could not get service instance for %s: %s', info.service_uuid, e)
                    del storage_dict[key]
                    continue

                if (count := count + 1) > consts.MAX_DELETIONS_AT_ONCE:
                    break

                del storage_dict[key]  # Remove from storage, being processed

                # Only add if not too many retries already
                infos.append(info)
        return services, infos

    @staticmethod
    def count_from_storage(group: types.DeferredStorageGroup) -> int:
        # Counts the total number of objects in storage
        with DeletionInfo.deferred_storage.as_dict(group) as storage_dict:
            return len(storage_dict)
        

    @staticmethod
    def csv_header() -> str:
        return 'vmid,created,next_check,service_uuid,fatal_retries,total_retries,retries'

    @staticmethod
    def report(out: typing.TextIO) -> None:
        """
        Generates a report of the current state of the deferred deletion
        """
        out.write(DeletionInfo.csv_header() + '\n')
        for group in DeferredStorageGroup:
            with DeletionInfo.deferred_storage.as_dict(group) as storage_dict:
                info: tuple[str, DeletionInfo]
                for info in storage_dict.unlocked_items():
                    out.write(info[0] + ',' + info[1].as_csv() + '\n')
