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
import typing
import logging

from uds.core.jobs import Job
from uds.core.util import utils
from uds.core.consts import deferred_deletion as consts
from uds.core.types import deferred_deletion as types

from uds.core.services.generics import exceptions as gen_exceptions

if typing.TYPE_CHECKING:
    from uds.core.services.generics.dynamic.service import DynamicService

logger = logging.getLogger(__name__)


def execution_timer() -> 'utils.ExecutionTimer':
    """
    Generates an execution timer for deletion operations
    This allows to delay the next check based on how long the operation took
    """
    return utils.ExecutionTimer(
        delay_threshold=consts.OPERATION_DELAY_THRESHOLD, max_delay_rate=consts.MAX_DELAY_RATE
    )


class DeferredDeletionWorker(Job):
    frecuency = 7  # Frequency for this job, in seconds
    friendly_name = 'Deferred deletion runner'

    @staticmethod
    def add(service: 'DynamicService', vmid: str, execute_later: bool = False) -> None:
        logger.debug('Adding %s from service %s to deferred deletion', vmid, service.type_name)
        # If sync, execute now
        if not execute_later:
            exec_time = execution_timer()
            try:
                with exec_time:
                    if service.must_stop_before_deletion:
                        if service.is_running(None, vmid):
                            if service.should_try_soft_shutdown():
                                service.shutdown(None, vmid)
                            else:
                                service.stop(None, vmid)
                            types.DeletionInfo.create_on_storage(
                                types.DeferredStorageGroup.STOPPING, vmid, service.db_obj().uuid
                            )
                            return

                    service.execute_delete(vmid)
                # If this takes too long, we will delay the next check a bit
                types.DeletionInfo.create_on_storage(
                    types.DeferredStorageGroup.DELETING,
                    vmid,
                    service.db_obj().uuid,
                    delay_rate=exec_time.delay_rate,
                )
            except gen_exceptions.NotFoundError:
                return  # Already removed
            except Exception as e:
                logger.warning(
                    'Could not delete %s from service %s: %s. Retrying later.', vmid, service.db_obj().name, e
                )
                types.DeletionInfo.create_on_storage(
                    types.DeferredStorageGroup.TO_DELETE,
                    vmid,
                    service.db_obj().uuid,
                    delay_rate=exec_time.delay_rate,
                )
                return
        else:
            if service.must_stop_before_deletion:
                types.DeletionInfo.create_on_storage(types.DeferredStorageGroup.TO_STOP, vmid, service.db_obj().uuid)
            else:
                types.DeletionInfo.create_on_storage(
                    types.DeferredStorageGroup.TO_DELETE, vmid, service.db_obj().uuid
                )
            return

    def _process_exception(
        self,
        info: types.DeletionInfo,
        to_group: types.DeferredStorageGroup,
        services: dict[str, 'DynamicService'],
        e: Exception,
        *,
        delay_rate: float = 1.0,
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

        if not is_retryable:
            info.next_check = types.DeletionInfo.next_execution_calculator(fatal=True, delay_rate=delay_rate)
            info.fatal_retries += 1
            if info.fatal_retries >= consts.MAX_FATAL_ERROR_RETRIES:
                logger.error(
                    'Fatal error deleting %s from service %s, removing from deferred deletion',
                    info.vmid,
                    services[info.service_uuid].db_obj().name,
                )
                return  # Do not readd it
        info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=delay_rate)
        info.total_retries += 1
        if info.total_retries >= consts.MAX_RETRAYABLE_ERROR_RETRIES:
            logger.error(
                'Too many retries deleting %s from service %s, removing from deferred deletion',
                info.vmid,
                services[info.service_uuid].db_obj().name,
            )
            return  # Do not readd it
        info.sync_to_storage(to_group)

    def process_to_stop(self) -> None:
        services, to_stop = types.DeletionInfo.get_from_storage(types.DeferredStorageGroup.TO_STOP)
        logger.debug('Processing %s to stop', to_stop)

        # Now process waiting stops
        for info in to_stop:  # Key not used
            exec_time = execution_timer()
            try:
                service = services[info.service_uuid]
                if service.must_stop_before_deletion is False:
                    info.sync_to_storage(types.DeferredStorageGroup.TO_DELETE)
                    continue
                with exec_time:
                    if service.is_running(None, info.vmid):
                        # if info.retries < RETRIES_TO_RETRY, means this is the first time we try to stop it
                        if info.retries < consts.RETRIES_TO_RETRY:
                            if service.should_try_soft_shutdown():
                                service.shutdown(None, info.vmid)
                            else:
                                service.stop(None, info.vmid)
                            info.fatal_retries = info.total_retries = 0
                        else:
                            info.total_retries += 1  # Count this as a general retry
                            info.retries = 0  # Reset retries
                            service.stop(None, info.vmid)  # Always try to stop it if we have tried before

                        info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=exec_time.delay_rate)
                        info.sync_to_storage(types.DeferredStorageGroup.STOPPING)
                    else:
                        # Do not update last_check to shutdown it asap, was not running after all
                        info.sync_to_storage(types.DeferredStorageGroup.TO_DELETE)
            except Exception as e:
                self._process_exception(
                    info, types.DeferredStorageGroup.TO_STOP, services, e, delay_rate=exec_time.delay_rate
                )

    def process_stopping(self) -> None:
        services, stopping = types.DeletionInfo.get_from_storage(types.DeferredStorageGroup.STOPPING)
        logger.debug('Processing %s stopping', stopping)

        # Now process waiting for finishing stops
        for info in stopping:
            exec_time = execution_timer()
            try:
                info.retries += 1
                if info.retries > consts.RETRIES_TO_RETRY:
                    # If we have tried to stop it, and it has not stopped, add to stop again
                    info.next_check = types.DeletionInfo.next_execution_calculator()
                    info.total_retries += 1
                    info.sync_to_storage(types.DeferredStorageGroup.TO_STOP)
                    continue
                with exec_time:
                    if services[info.service_uuid].is_running(None, info.vmid):
                        info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=exec_time.delay_rate)
                        info.total_retries += 1
                        info.sync_to_storage(types.DeferredStorageGroup.STOPPING)
                    else:
                        info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=exec_time.delay_rate)
                        info.fatal_retries = info.total_retries = 0
                        info.sync_to_storage(types.DeferredStorageGroup.TO_DELETE)
            except Exception as e:
                self._process_exception(
                    info, types.DeferredStorageGroup.STOPPING, services, e, delay_rate=exec_time.delay_rate
                )

    def process_to_delete(self) -> None:
        services, to_delete = types.DeletionInfo.get_from_storage(types.DeferredStorageGroup.TO_DELETE)
        logger.debug('Processing %s to delete', to_delete)

        # Now process waiting deletions
        for info in to_delete:
            service = services[info.service_uuid]
            exec_time = execution_timer()
            try:
                with exec_time:
                    # If must be stopped before deletion, and is running, put it on to_stop
                    if service.must_stop_before_deletion and service.is_running(None, info.vmid):
                        info.sync_to_storage(types.DeferredStorageGroup.TO_STOP)
                        continue

                    service.execute_delete(info.vmid)
                # And store it for checking later if it has been deleted, reseting counters
                info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=exec_time.delay_rate)
                info.retries = 0
                info.total_retries += 1
                info.sync_to_storage(types.DeferredStorageGroup.DELETING)
            except Exception as e:
                self._process_exception(
                    info,
                    types.DeferredStorageGroup.TO_DELETE,
                    services,
                    e,
                    delay_rate=exec_time.delay_rate,
                )

    def process_deleting(self) -> None:
        """
        Process all deleting objects, and remove them if they are already deleted

        Note: Very similar to process_to_delete, but this one is for objects that are already being deleted
        """
        services, deleting = types.DeletionInfo.get_from_storage(types.DeferredStorageGroup.DELETING)
        logger.debug('Processing %s deleting', deleting)

        # Now process waiting for finishing deletions
        for info in deleting:  # Key not used
            exec_time = execution_timer()
            try:
                info.retries += 1
                if info.retries > consts.RETRIES_TO_RETRY:
                    # If we have tried to delete it, and it has not been deleted, add to delete again
                    info.next_check = types.DeletionInfo.next_execution_calculator()
                    info.total_retries += 1
                    info.sync_to_storage(types.DeferredStorageGroup.TO_DELETE)
                    continue
                with exec_time:
                    # If not finished, readd it for later check
                    if not services[info.service_uuid].is_deleted(info.vmid):
                        info.next_check = types.DeletionInfo.next_execution_calculator(delay_rate=exec_time.delay_rate)
                        info.total_retries += 1
                        info.sync_to_storage(types.DeferredStorageGroup.DELETING)
                    else:
                        # Deletion is finished, notify to service
                        services[info.service_uuid].notify_deleted(info.vmid)
            except Exception as e:
                self._process_exception(
                    info, types.DeferredStorageGroup.DELETING, services, e, delay_rate=exec_time.delay_rate
                )

    def run(self) -> None:
        self.process_to_stop()
        self.process_stopping()
        self.process_to_delete()
        self.process_deleting()

    # To allow reporting what is on the queues
    @staticmethod
    def report(out: typing.TextIO) -> None:
        out.write(types.DeletionInfo.csv_header() + '\n')
        for group in types.DeferredStorageGroup:
            with types.DeletionInfo.deferred_storage.as_dict(group) as storage:
                for _key, info in typing.cast(dict[str, types.DeletionInfo], storage).items():
                    out.write(info.as_csv() + '\n')
        out.write('\n')
