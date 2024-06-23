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
import dataclasses
import collections.abc
import datetime
import typing
import logging

from uds.models import Service
from uds.core.util.model import sql_now
from uds.core.jobs import Job
from uds.core.util import storage

from uds.core.services.generics import exceptions as gen_exceptions

if typing.TYPE_CHECKING:
    from uds.core.services.generics.dynamic.service import DynamicService

logger = logging.getLogger(__name__)


MAX_FATAL_ERROR_RETRIES: typing.Final[int] = 8
MAX_TOTAL_RETRIES: typing.Final[int] = 1024
MAX_DELETIONS_AT_ONCE: typing.Final[int] = 16
MAX_DELETIONS_CHECKED_AT_ONCE: typing.Final[int] = MAX_DELETIONS_AT_ONCE * 2

CHECK_INTERVAL: typing.Final[int] = 32  # Check interval, in seconds

TO_DELETE_GROUP: typing.Final[str] = 'to_delete'
DELETING_GROUP: typing.Final[str] = 'deleting'


@dataclasses.dataclass
class DeferredDeletionInfo:
    vmid: str
    created: datetime.datetime
    last_check: datetime.datetime
    service_uuid: str
    fatal_retries: int = 0  # Fatal error retries
    total_retries: int = 0  # Total retries


class DeferredDeletionWorker(Job):
    frecuency = 32  # Frecuncy for this job, in seconds
    friendly_name = 'Deferred deletion runner'

    deferred_storage: typing.ClassVar[storage.Storage] = storage.Storage('deferdel_worker')

    @staticmethod
    def add(service: 'DynamicService', vmid: str, execute_later: bool = False) -> None:
        # First, try sync deletion
        unique_key = f'{service.db_obj().uuid}_{vmid}'

        def _add_for_later() -> None:
            with DeferredDeletionWorker.deferred_storage.as_dict(TO_DELETE_GROUP, atomic=True) as storage_dict:
                storage_dict[unique_key] = DeferredDeletionInfo(
                    vmid=vmid,
                    created=sql_now(),
                    last_check=sql_now(),
                    service_uuid=service.db_obj().uuid,
                )

        if not execute_later:
            try:
                service.execute_delete(vmid)
            except gen_exceptions.NotFoundError:
                return  # Already removed
            except Exception as e:
                logger.warning(
                    'Could not delete %s from service %s: %s. Retrying later.', vmid, service.db_obj().name, e
                )
                _add_for_later()
                return
        else:
            _add_for_later()
            return

        # Has not been deleted, so we will defer deletion
        with DeferredDeletionWorker.deferred_storage.as_dict(DELETING_GROUP, atomic=True) as storage_dict:
            storage_dict[unique_key] = DeferredDeletionInfo(
                vmid=vmid,
                created=sql_now(),
                last_check=sql_now(),
                service_uuid=service.db_obj().uuid,
            )

    def _get_from_storage(
        self, storage_name: str
    ) -> tuple[dict[str, 'DynamicService'], list[tuple[str, DeferredDeletionInfo]]]:
        # Get all wating deletion, and try it
        count = 0
        infos: list[tuple[str, DeferredDeletionInfo]] = []

        services: dict[str, 'DynamicService'] = {}

        # First, get ownership of to_delete objects to be processed
        # We do this way to release db locks as soon as possible
        with DeferredDeletionWorker.deferred_storage.as_dict(storage_name, atomic=True) as storage_dict:
            for key, info in sorted(
                typing.cast(collections.abc.Iterable[tuple[str, DeferredDeletionInfo]], storage_dict.items()),
                key=lambda x: x[1].last_check,
            ):
                service: typing.Optional['DynamicService'] = None

                if info.last_check + datetime.timedelta(seconds=CHECK_INTERVAL) > sql_now():
                    continue
                try:
                    if info.service_uuid not in services:
                        service = typing.cast(
                            'DynamicService', Service.objects.get(uuid=info.service_uuid).get_instance()
                        )
                except Exception as e:
                    logger.error('Could not get service instance for %s: %s', info.service_uuid, e)
                    del storage_dict[key]
                    continue

                count += 1
                if count > MAX_DELETIONS_AT_ONCE:
                    break

                if service is not None:
                    services[info.service_uuid] = service

                infos.append((key, info))
                del storage_dict[key]  # Remove from storage, being processed
        return services, infos

    def _process_exception(
        self,
        key: str,
        info: DeferredDeletionInfo,
        group: str,
        services: dict[str, 'DynamicService'],
        e: Exception,
    ) -> None:
        if isinstance(e, gen_exceptions.NotFoundError):
            return  # All ok, already removed

        is_retryable = isinstance(e, gen_exceptions.RetryableError)
        logger.error(
            'Error deleting %s from service %s: %s%s',
            info.vmid,
            services[info.service_uuid].db_obj().name,
            e,
            ' (will retry)' if is_retryable else '',
        )
        info.last_check = sql_now()
        if not is_retryable:
            info.fatal_retries += 1
            if info.fatal_retries >= MAX_FATAL_ERROR_RETRIES:
                logger.error(
                    'Fatal error deleting %s from service %s, removing from deferred deletion',
                    info.vmid,
                    services[info.service_uuid].db_obj().name,
                )
                return  # Do not readd it
        info.total_retries += 1
        if info.total_retries >= MAX_TOTAL_RETRIES:
            logger.error(
                'Too many retries deleting %s from service %s, removing from deferred deletion',
                info.vmid,
                services[info.service_uuid].db_obj().name,
            )
            return  # Do not readd it
        with DeferredDeletionWorker.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            storage_dict[key] = info

    def process_to_delete(self) -> None:
        services, to_delete = self._get_from_storage(TO_DELETE_GROUP)

        # Now process waiting deletions
        for key, info in to_delete:
            try:
                services[info.service_uuid].execute_delete(info.vmid)
                # And store it for checking later if it has been deleted, reseting counters
                with DeferredDeletionWorker.deferred_storage.as_dict(
                    DELETING_GROUP, atomic=True
                ) as storage_dict:
                    info.last_check = sql_now()
                    info.fatal_retries = 0
                    info.total_retries = 0
                    storage_dict[key] = info
            except Exception as e:
                self._process_exception(key, info, TO_DELETE_GROUP, services, e)

    def process_deleting(self) -> None:
        """
        Process all deleting objects, and remove them if they are already deleted

        Note: Very similar to process_to_delete, but this one is for objects that are already being deleted
        """
        services, deleting = self._get_from_storage(DELETING_GROUP)

        # Now process waiting deletions checks
        for key, info in deleting:
            try:
                # If not finished, readd it for later check
                if not services[info.service_uuid].is_deleted(info.vmid):
                    info.last_check = sql_now()
                    info.total_retries += 1
                    with DeferredDeletionWorker.deferred_storage.as_dict(
                        DELETING_GROUP, atomic=True
                    ) as storage_dict:
                        storage_dict[key] = info
            except Exception as e:
                self._process_exception(key, info, DELETING_GROUP, services, e)

    def run(self) -> None:
        self.process_to_delete()
        self.process_deleting()
