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


MAX_FATAL_ERROR_RETRIES: typing.Final[int] = 16
MAX_RETRAYABLE_ERROR_RETRIES: typing.Final[int] = 8192   # Max retries before giving up at most 72 hours
RETRIES_TO_RETRY: typing.Final[int] = (
    32  # Retries to stop again or to shutdown again in STOPPING_GROUP or DELETING_GROUP
)
MAX_DELETIONS_AT_ONCE: typing.Final[int] = 32
MAX_DELETIONS_CHECKED_AT_ONCE: typing.Final[int] = MAX_DELETIONS_AT_ONCE * 2

# This interval is how long will take to check again for deletion, stopping, etc...
# That is, once a machine is deleted, every 32 seconds will be check that it has been deleted
CHECK_INTERVAL: typing.Final[int] = 32  # Check interval, in seconds

TO_STOP_GROUP: typing.Final[str] = 'to_stop'
STOPPING_GROUP: typing.Final[str] = 'stopping'
TO_DELETE_GROUP: typing.Final[str] = 'to_delete'
DELETING_GROUP: typing.Final[str] = 'deleting'


@dataclasses.dataclass
class DeletionInfo:
    vmid: str
    created: datetime.datetime
    last_check: datetime.datetime
    service_uuid: str
    fatal_retries: int = 0  # Fatal error retries
    total_retries: int = 0  # Total retries
    retries: int = 0  # Retries to stop again or to delete again in STOPPING_GROUP or DELETING_GROUP

    def sync_to_storage(self, group: str) -> None:
        """
        Ensures that this object is stored on the storage
        If exists, it will be updated, if not, it will be created
        """
        unique_key = f'{self.service_uuid}_{self.vmid}'
        with DeferredDeletionWorker.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            storage_dict[unique_key] = self

    @staticmethod
    def create_on_storage(group: str, vmid: str, service_uuid: str) -> None:
        unique_key = f'{service_uuid}_{vmid}'
        with DeferredDeletionWorker.deferred_storage.as_dict(group, atomic=True) as storage_dict:
            storage_dict[unique_key] = DeletionInfo(
                vmid=vmid,
                created=sql_now(),
                last_check=sql_now(),
                service_uuid=service_uuid,
                # fatal, total an retries are 0 by default
            )

    @staticmethod
    def get_from_storage(
        storage_name: str,
    ) -> tuple[dict[str, 'DynamicService'], list[tuple[str, 'DeletionInfo']]]:
        """
        Get a list of objects to be processed from storage

        Note:
            This method will remove the objects from storage, so if needed, has to be readded
            This is so we can release locks as soon as possible
        """
        count = 0
        infos: list[tuple[str, DeletionInfo]] = []

        services: dict[str, 'DynamicService'] = {}

        # First, get ownership of to_delete objects to be processed
        # We do this way to release db locks as soon as possible
        with DeferredDeletionWorker.deferred_storage.as_dict(storage_name, atomic=True) as storage_dict:
            for key, info in sorted(
                typing.cast(collections.abc.Iterable[tuple[str, DeletionInfo]], storage_dict.items()),
                key=lambda x: x[1].last_check,
            ):
                # if max retries reached, remove it
                if info.total_retries >= MAX_RETRAYABLE_ERROR_RETRIES:
                    logger.error(
                        'Too many retries deleting %s from service %s, removing from deferred deletion',
                        info.vmid,
                        info.service_uuid,
                    )
                    del storage_dict[key]
                    continue

                if info.last_check + datetime.timedelta(seconds=CHECK_INTERVAL) > sql_now():
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

                if (count := count + 1) > MAX_DELETIONS_AT_ONCE:
                    break

                del storage_dict[key]  # Remove from storage, being processed

                # Only add if not too many retries already
                infos.append((key, info))
        return services, infos


class DeferredDeletionWorker(Job):
    frecuency = 11  # Frequency for this job, in seconds
    friendly_name = 'Deferred deletion runner'

    deferred_storage: typing.ClassVar[storage.Storage] = storage.Storage('deferdel_worker')

    @staticmethod
    def add(service: 'DynamicService', vmid: str, execute_later: bool = False) -> None:
        logger.debug('Adding %s from service %s to deferred deletion', vmid, service.type_name)
        # If sync, execute now
        if not execute_later:
            try:
                if service.must_stop_before_deletion:
                    if service.is_running(None, vmid):
                        if service.should_try_soft_shutdown():
                            service.shutdown(None, vmid)
                        else:
                            service.stop(None, vmid)
                        DeletionInfo.create_on_storage(STOPPING_GROUP, vmid, service.db_obj().uuid)
                        return

                service.execute_delete(vmid)
            except gen_exceptions.NotFoundError:
                return  # Already removed
            except Exception as e:
                logger.warning(
                    'Could not delete %s from service %s: %s. Retrying later.', vmid, service.db_obj().name, e
                )
                DeletionInfo.create_on_storage(TO_DELETE_GROUP, vmid, service.db_obj().uuid)
                return
        else:
            if service.must_stop_before_deletion:
                DeletionInfo.create_on_storage(TO_STOP_GROUP, vmid, service.db_obj().uuid)
            else:
                DeletionInfo.create_on_storage(TO_DELETE_GROUP, vmid, service.db_obj().uuid)
            return

        # Has not been deleted, so we will defer deletion
        DeletionInfo.create_on_storage(DELETING_GROUP, vmid, service.db_obj().uuid)

    def _process_exception(
        self,
        key: str,
        info: DeletionInfo,
        to_group: str,
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
        if info.total_retries >= MAX_RETRAYABLE_ERROR_RETRIES:
            logger.error(
                'Too many retries deleting %s from service %s, removing from deferred deletion',
                info.vmid,
                services[info.service_uuid].db_obj().name,
            )
            return  # Do not readd it
        info.sync_to_storage(to_group)

    def process_to_stop(self) -> None:
        services, to_stop = DeletionInfo.get_from_storage(TO_STOP_GROUP)
        logger.debug('Processing %s to stop', to_stop)

        # Now process waiting stops
        for key, info in to_stop:
            try:
                service = services[info.service_uuid]
                if service.is_running(None, info.vmid):
                    # if info.retries < RETRIES_TO_RETRY, means this is the first time we try to stop it
                    if info.retries < RETRIES_TO_RETRY:
                        if service.should_try_soft_shutdown():
                            service.shutdown(None, info.vmid)
                        else:
                            service.stop(None, info.vmid)
                        info.fatal_retries = info.total_retries = 0
                    else:
                        info.total_retries += 1  # Count this as a general retry
                        info.retries = 0  # Reset retries
                        service.stop(None, info.vmid)  # Always try to stop it if we have tried before

                    info.last_check = sql_now()
                    info.sync_to_storage(STOPPING_GROUP)
                else:
                    # Do not update last_check to shutdown it asap, was not running after all
                    info.sync_to_storage(TO_DELETE_GROUP)
            except Exception as e:
                self._process_exception(key, info, TO_STOP_GROUP, services, e)

    def process_stopping(self) -> None:
        services, stopping = DeletionInfo.get_from_storage(STOPPING_GROUP)
        logger.debug('Processing %s stopping', stopping)

        # Now process waiting for finishing stops
        for key, info in stopping:
            try:
                info.retries += 1
                if info.retries > RETRIES_TO_RETRY:
                    # If we have tried to stop it, and it has not stopped, add to stop again
                    info.last_check = sql_now()
                    info.total_retries += 1
                    info.sync_to_storage(TO_STOP_GROUP)
                    continue

                if services[info.service_uuid].is_running(None, info.vmid):
                    info.last_check = sql_now()
                    info.total_retries += 1
                    info.sync_to_storage(STOPPING_GROUP)
                else:
                    info.last_check = sql_now()
                    info.fatal_retries = info.total_retries = 0
                    info.sync_to_storage(TO_DELETE_GROUP)
            except Exception as e:
                self._process_exception(key, info, STOPPING_GROUP, services, e)

    def process_to_delete(self) -> None:
        services, to_delete = DeletionInfo.get_from_storage(TO_DELETE_GROUP)
        logger.debug('Processing %s to delete', to_delete)

        # Now process waiting deletions
        for key, info in to_delete:
            service = services[info.service_uuid]
            try:
                # If must be stopped before deletion, and is running, put it on to_stop
                if service.must_stop_before_deletion and service.is_running(None, info.vmid):
                    info.sync_to_storage(TO_STOP_GROUP)
                    continue

                service.execute_delete(info.vmid)
                # And store it for checking later if it has been deleted, reseting counters
                info.last_check = sql_now()
                info.retries = 0
                info.total_retries += 1
                info.sync_to_storage(DELETING_GROUP)
            except Exception as e:
                self._process_exception(key, info, TO_DELETE_GROUP, services, e)

    def process_deleting(self) -> None:
        """
        Process all deleting objects, and remove them if they are already deleted

        Note: Very similar to process_to_delete, but this one is for objects that are already being deleted
        """
        services, deleting = DeletionInfo.get_from_storage(DELETING_GROUP)
        logger.debug('Processing %s deleting', deleting)

        # Now process waiting for finishing deletions
        for key, info in deleting:
            try:
                info.retries += 1
                if info.retries > RETRIES_TO_RETRY:
                    # If we have tried to delete it, and it has not been deleted, add to delete again
                    info.last_check = sql_now()
                    info.total_retries += 1
                    info.sync_to_storage(TO_DELETE_GROUP)
                    continue

                # If not finished, readd it for later check
                if not services[info.service_uuid].is_deleted(info.vmid):
                    info.last_check = sql_now()
                    info.total_retries += 1
                    info.sync_to_storage(DELETING_GROUP)
            except Exception as e:
                self._process_exception(key, info, DELETING_GROUP, services, e)

    def run(self) -> None:
        self.process_to_stop()
        self.process_stopping()
        self.process_to_delete()
        self.process_deleting()
