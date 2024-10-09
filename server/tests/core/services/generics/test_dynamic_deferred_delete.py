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
Authot: Adolfo Gómez, dkmaster at dkmon dot com
"""
import contextlib
import datetime
import itertools
import typing
from unittest import mock

from uds import models
from uds.core import services
from uds.core.util.model import sql_now
from uds.workers import deferred_deleter
from uds.core.services.generics import exceptions as gen_exceptions

from uds.core.consts import deferred_deletion as deferred_consts
from uds.core.types import deferred_deletion as deferred_types

from ....utils.test import UDSTransactionTestCase
from ....utils import helpers
from . import fixtures


class DynamicDeferredDeleteTest(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()

        services.factory().insert(fixtures.DynamicTestingProvider)

    def set_last_check_expired(self) -> None:
        for group in deferred_types.DeferredStorageGroup:
            with deferred_types.DeletionInfo.deferred_storage.as_dict(group) as storage:
                for key, info in typing.cast(dict[str, deferred_types.DeletionInfo], storage).items():
                    info.next_check = sql_now() - datetime.timedelta(seconds=1)
                    storage[key] = info

    def count_entries_on_storage(self, group: str) -> int:
        with deferred_types.DeletionInfo.deferred_storage.as_dict(group) as storage:
            return len(storage)

    @contextlib.contextmanager
    def patch_for_worker(
        self,
        *,
        execute_delete_side_effect: typing.Union[None, typing.Callable[..., None], Exception] = None,
        is_deleted_side_effect: typing.Union[None, typing.Callable[..., bool], Exception] = None,
        is_running: typing.Union[None, typing.Callable[..., bool]] = None,
        must_stop_before_deletion: bool = False,
        should_try_soft_shutdown: bool = False,
    ) -> typing.Iterator[tuple[mock.MagicMock, dict[str, dict[str, deferred_types.DeletionInfo]]]]:
        """
        Patch the storage to use a dict instead of the real storage

        This is useful to test the worker without touching the real storage
        """
        dct: dict[str, dict[str, deferred_types.DeletionInfo]] = {}
        instance = mock.MagicMock()
        instance_db_obj = mock.MagicMock(uuid='service1')
        instance_db_obj.get_instance.return_value = instance
        instance.db_obj.return_value = instance_db_obj
        instance.execute_delete.side_effect = execute_delete_side_effect or helpers.returns_none
        instance.is_deleted.side_effect = is_deleted_side_effect or helpers.returns_true

        instance.must_stop_before_deletion = must_stop_before_deletion
        instance.should_try_soft_shutdown.return_value = should_try_soft_shutdown
        instance.is_running.side_effect = is_running or helpers.returns_false
        instance.stop.return_value = None
        instance.shutdown.return_value = None

        # Patchs uds.models.Service also for get_instance to work
        with mock.patch('uds.models.Service.objects') as objs:
            objs.get.return_value = instance.db_obj()
            with mock.patch(
                'uds.core.types.deferred_deletion.DeletionInfo.deferred_storage'
            ) as storage:

                @contextlib.contextmanager
                def _as_dict(
                    group: str, *args: typing.Any, **kwargs: typing.Any
                ) -> typing.Iterator[dict[str, deferred_types.DeletionInfo]]:
                    if group not in dct:
                        dct[group] = {}
                    yield dct[group]

                storage.as_dict.side_effect = _as_dict
                yield instance, dct

    def test_delete_full_fine_delete(self) -> None:
        # Tests only delete and is_deleted, no stop and stopping

        service = fixtures.create_dynamic_service_for_deferred_deletion()

        provider = models.Provider.objects.create(
            name='provider1',
            comments='c provider1',
            data_type=service.provider().type_type,
            data=service.provider().serialize(),
        )

        services: list[models.Service] = [
            models.Service.objects.create(
                name=f'service_{i}',
                provider=provider,
                data_type=service.type_type,
                data=service.serialize(),
            )
            for i in range(8)
        ]

        # Ensure get_instance works fine, and call delete for each one
        for count, service in enumerate(services):
            instance = typing.cast(fixtures.DynamicTestingServiceForDeferredDeletion, service.get_instance())
            self.assertIsInstance(instance, fixtures.DynamicTestingServiceForDeferredDeletion)
            instance.delete(mock.MagicMock(), f'vmid_{count}_1')
            instance.mock.execute_delete.assert_called_with(f'vmid_{count}_1')
            # Add a second delete, so can check service caching later
            instance.delete(mock.MagicMock(), f'vmid_{count}_2')
            instance.mock.execute_delete.assert_called_with(f'vmid_{count}_2')

        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.execute_delete.call_count, 16)
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.is_deleted.call_count, 0)
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.notify_deleted.call_count, 0)
        # Reset mock
        fixtures.DynamicTestingServiceForDeferredDeletion.mock.reset_mock()

        # No entries into to_delete, nor TO_STOP nor STOPPING
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.STOPPING), 0)

        # Storage db should have 16 entries
        with deferred_types.DeletionInfo.deferred_storage.as_dict(
            deferred_types.DeferredStorageGroup.DELETING
        ) as deleting:
            self.assertEqual(len(deleting), 16)
            for key, info in typing.cast(dict[str, deferred_types.DeletionInfo], deleting).items():
                now = sql_now()
                self.assertIsInstance(info, deferred_types.DeletionInfo)
                self.assertEqual(key, f'{info.service_uuid}_{info.vmid}')
                self.assertLessEqual(info.created, now)
                self.assertGreaterEqual(info.next_check, now)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 0)

        # Instantiate the Job
        job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
        to_delete = deferred_types.DeletionInfo.get_from_storage(deferred_types.DeferredStorageGroup.TO_DELETE)
        # Should be empty, both services and infos
        self.assertEqual(len(to_delete[0]), 0)
        self.assertEqual(len(to_delete[1]), 0)

        # Now, get from deleting
        deleting = deferred_types.DeletionInfo.get_from_storage(deferred_types.DeferredStorageGroup.DELETING)
        # Should have o services and infos also, because last_check has been too soon
        self.assertEqual(len(deleting[0]), 0)
        self.assertEqual(len(deleting[1]), 0)

        # Update last_check for all entries and recheck
        self.set_last_check_expired()

        # Now, get from deleting again, should have all services and infos
        # OVerride MAX_DELETIONS_AT_ONCE to get only 1 entries
        deferred_consts.MAX_DELETIONS_AT_ONCE = 1
        services_1, key_info_1 = deferred_types.DeletionInfo.get_from_storage(
            deferred_types.DeferredStorageGroup.DELETING
        )
        self.assertEqual(len(services_1), 1)
        self.assertEqual(len(key_info_1), 1)
        # And should rest only 15 on storage
        with deferred_types.DeletionInfo.deferred_storage.as_dict(
            deferred_types.DeferredStorageGroup.DELETING
        ) as deleting:
            self.assertEqual(len(deleting), 15)
        deferred_consts.MAX_DELETIONS_AT_ONCE = 16
        services_2, key_info_2 = deferred_types.DeletionInfo.get_from_storage(
            deferred_types.DeferredStorageGroup.DELETING
        )
        self.assertEqual(len(services_2), 8)  # 8 services must be returned
        self.assertEqual(len(key_info_2), 15)  # And 15 entries

        # Re-store all DELETING_GROUP entries
        with deferred_types.DeletionInfo.deferred_storage.as_dict(
            deferred_types.DeferredStorageGroup.DELETING
        ) as deleting:
            for info in itertools.chain(key_info_1, key_info_2):
                deleting[info.key] = info

        # set MAX_DELETIONS_AT_ONCE to a value bigger than 16
        deferred_consts.MAX_DELETIONS_AT_ONCE = 100

        # Now, process all entries normally
        job.run()

        # Should have called is_deleted 16 times
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.is_deleted.call_count, 16)
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.notify_deleted.call_count, 16)
        # And should have removed all entries from deleting, because is_deleted returns True
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)

    def test_delete_delayed_full(self) -> None:
        service = fixtures.create_dynamic_service_for_deferred_deletion()

        provider = models.Provider.objects.create(
            name='provider1',
            comments='c provider1',
            data_type=service.provider().type_type,
            data=service.provider().serialize(),
        )

        service = models.Service.objects.create(
            name=f'service_1',
            provider=provider,
            data_type=service.type_type,
            data=service.serialize(),
        )

        instance = typing.cast(fixtures.DynamicTestingServiceForDeferredDeletion, service.get_instance())
        self.assertIsInstance(instance, fixtures.DynamicTestingServiceForDeferredDeletion)

        # Invoke add on worker with "execute_later" set to True, should not call execute_delete
        deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid_1', execute_later=True)
        instance.mock.execute_delete.assert_not_called()

        # No entries deleting
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
        # to_delete should contain one entry
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 1)

        job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
        to_delete = deferred_types.DeletionInfo.get_from_storage(deferred_types.DeferredStorageGroup.TO_DELETE)
        # Should be empty, both services and infos
        self.assertEqual(len(to_delete[0]), 0)
        self.assertEqual(len(to_delete[1]), 0)

        # Update the last_check for the entry and recheck
        self.set_last_check_expired()

        # Now, get from deleting again, should have all services and infos
        services, info = deferred_types.DeletionInfo.get_from_storage(deferred_types.DeferredStorageGroup.TO_DELETE)
        self.assertEqual(len(services), 1)
        self.assertEqual(len(info), 1)
        # now, db should be empty
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)

        # Re store the entry
        with deferred_types.DeletionInfo.deferred_storage.as_dict(
            deferred_types.DeferredStorageGroup.TO_DELETE
        ) as to_delete:
            for info in info:
                to_delete[info.key] = info

        # Process should move from to_delete to deleting
        job.run()  # process_to_delete and process_deleting

        # Should have called execute_delete once
        instance.mock.execute_delete.assert_called_once_with('vmid_1')
        # And should have removed all entries from to_delete
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 1)

        instance.mock.reset_mock()
        # And should have one entry in deleting
        with deferred_types.DeletionInfo.deferred_storage.as_dict(
            deferred_types.DeferredStorageGroup.DELETING
        ) as deleting:
            self.assertEqual(len(deleting), 1)
            for key, info in typing.cast(dict[str, deferred_types.DeletionInfo], deleting).items():
                now = sql_now()
                self.assertIsInstance(info, deferred_types.DeletionInfo)
                self.assertEqual(key, f'{info.service_uuid}_{info.vmid}')
                self.assertLessEqual(info.created, now)
                self.assertGreaterEqual(info.next_check, now)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 1)

        # And no call to is_deleted nor notify_deleted
        instance.mock.is_deleted.assert_not_called()
        instance.mock.notify_deleted.assert_not_called()

        # Executing now, should do nothing because last_check is not expired
        job.run()

        # Should have called is_deleted 0 times, due to last_check not expired
        instance.mock.is_deleted.assert_not_called()
        instance.mock.notify_deleted.assert_not_called()

        self.set_last_check_expired()  # So deleting gets processed

        job.run()

        # Now should have called is_deleted once, and no entries in deleting nor to_delete
        instance.mock.is_deleted.assert_called_once_with('vmid_1')
        instance.mock.notify_deleted.assert_called_once_with('vmid_1')
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)

    def test_deletion_is_deleted(self) -> None:
        for is_deleted in (True, False):
            with self.patch_for_worker(
                is_deleted_side_effect=lambda *args: is_deleted,
            ) as (instance, dct):
                deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

                # No entries in TO_DELETE_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                # One entry in DELETING_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 1)

                info = next(iter(dct[deferred_types.DeferredStorageGroup.DELETING].values()))

                # Fix last_check
                self.set_last_check_expired()

                job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
                job.run()

                # Should have called is_deleted once
                instance.is_deleted.assert_called_once_with('vmid1')
                # if is_deleted returns True, should have removed the entry
                if is_deleted:
                    instance.notify_deleted.assert_called_once_with('vmid1')
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                else:
                    instance.notify_deleted.assert_not_called()
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 1)
                    # Also, info should have been updated
                    self.assertEqual(info.fatal_retries, 0)
                    self.assertEqual(info.total_retries, 1)

    def test_deletion_fails_add(self) -> None:
        for error in (
            gen_exceptions.RetryableError('error'),
            gen_exceptions.NotFoundError('error'),
            gen_exceptions.FatalError('error'),
        ):
            with self.patch_for_worker(
                execute_delete_side_effect=error,
            ) as (instance, dct):
                deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

                # Not found should remove the entry and nothing more
                if isinstance(error, gen_exceptions.NotFoundError):
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                    continue

                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 1)
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)

                info = next(iter(dct[deferred_types.DeferredStorageGroup.TO_DELETE].values()))  # Get first element
                self.assertEqual(info.vmid, 'vmid1')
                self.assertEqual(info.service_uuid, instance.db_obj().uuid)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 0)  # On adding & error, no count is increased

                job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
                job.run()
                # due to check_interval, no retries are done
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 1)
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)

                # Fix last_check
                self.set_last_check_expired()

                # And run again
                job.run()

                if isinstance(error, gen_exceptions.RetryableError):
                    self.assertEqual(info.fatal_retries, 0)
                    self.assertEqual(info.total_retries, 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                    # Test that MAX_TOTAL_RETRIES works fine
                    deferred_consts.MAX_RETRAYABLE_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                else:
                    self.assertEqual(info.fatal_retries, 1)
                    self.assertEqual(info.total_retries, 1)
                    # test that MAX_FATAL_RETRIES works fine
                    deferred_consts.MAX_FATAL_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)

    def test_deletion_fails_is_deleted(self) -> None:
        for error in (
            gen_exceptions.RetryableError('error'),
            gen_exceptions.NotFoundError('error'),
            gen_exceptions.FatalError('error'),
        ):
            with self.patch_for_worker(
                is_deleted_side_effect=error,
            ) as (instance, dct):
                deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

                # No entries in TO_DELETE_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                # One entry in DELETING_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 1)

                info = next(iter(dct[deferred_types.DeferredStorageGroup.DELETING].values()))

                # Fix last_check
                self.set_last_check_expired()

                job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
                job.run()

                # Should have called is_deleted once and notify_deleted not called
                instance.is_deleted.assert_called_once_with('vmid1')
                instance.notify_deleted.assert_not_called()

                if isinstance(error, gen_exceptions.RetryableError):
                    self.assertEqual(info.fatal_retries, 0)
                    self.assertEqual(info.total_retries, 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 1)
                    # Test that MAX_TOTAL_RETRIES works fine
                    deferred_consts.MAX_RETRAYABLE_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                elif isinstance(error, gen_exceptions.NotFoundError):
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
                else:
                    self.assertEqual(info.fatal_retries, 1)
                    self.assertEqual(info.total_retries, 1)
                    # test that MAX_FATAL_RETRIES works fine
                    deferred_consts.MAX_FATAL_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)

    def test_stop(self) -> None:

        # Explanation:
        # key: running, execute_later, should_try_soft_shutdown
        # TODELETE, DELETING, TO_STOP, STOPPING, is_running calls, stop calls, shutdown calls
        # group assignation:
        # * to TO_STOP  if execute_later is true (#1, #3, #5, #7), because is requested so (and service requires stop)
        # * to STOPPING if running and execute_later is false (#2, #4). If not running, no need to stop
        # * to DELETING if not running and execute_later is false (#6, #8). If running, just proceed to delete and store in the deleting group
        # calls:
        # * is running is called if no execute_later (#2, #4, #6, #8)
        # * stop is called if running and not execute_later and not should_try_soft_shutdown (#4)
        # * shutdown is called if running and not execute_later and should_try_soft_shutdown (#2)
        COUNTERS_ADD: typing.Final[dict[tuple[bool, bool, bool], tuple[int, int, int, int, int, int, int]]] = {
            # run   exec  try      TD DE TS ST is st sh
            (True, True, True): (0, 0, 1, 0, 0, 0, 0),  # 1
            (True, False, True): (0, 0, 0, 1, 1, 0, 1),  # 2
            (True, True, False): (0, 0, 1, 0, 0, 0, 0),  # 3
            (True, False, False): (0, 0, 0, 1, 1, 1, 0),  # 4
            (False, True, True): (0, 0, 1, 0, 0, 0, 0),  # 5
            (False, False, True): (0, 1, 0, 0, 1, 0, 0),  # 6
            (False, True, False): (0, 0, 1, 0, 0, 0, 0),  # 7
            (False, False, False): (0, 1, 0, 0, 1, 0, 0),  # 8
        }

        # Explanation:
        # key: running, execute_later, should_try_soft_shutdown
        # TODELETE, DELETING, TO_STOP, STOPPING, is_running calls, stop calls, shutdown calls
        # group assignation:
        # * to TO_DELETE is not used in this flow, because as soon as the vm is stopped, is added to this group and PROCESSED
        #   so, before exiting, it's already in the DELETING group
        # * to DELETING if not runing and execute_later is false (#6, #8). This is so because if not running. is moved to
        #   the TODELETE group, and processed inmediately before returning from job run
        # * to TO_STOP is never moved, because it's the first step and only assigned on "add" method
        # * to STOPPING will contain 1 item as long as the vm is running (#1, #2, #3, #4)
        # Note that #6 and #8 are all 0, because the procedure has been completed (remember comes from ADD #6 and #8, that was in DELETING)
        # calls:
        # * is running if comes from TO_STOP or STOPPING (#1, #2, #3, #4, #5 and #7)
        # * stop if running and execute later and not should_try_soft_shutdown (#1, #3, #5)
        # * shutdown if running and execute later and should_try_soft_shutdown (#2)
        COUNTERS_JOB: dict[tuple[bool, bool, bool], tuple[int, int, int, int, int, int, int]] = {
            # run   exec  try      TD DE TS ST is st sh
            (True, True, True): (0, 0, 0, 1, 1, 0, 1),  # 1
            (True, False, True): (0, 0, 0, 1, 1, 0, 0),  # 2
            (True, True, False): (0, 0, 0, 1, 1, 1, 0),  # 3
            (True, False, False): (0, 0, 0, 1, 1, 0, 0),  # 4
            (False, True, True): (0, 1, 0, 0, 2, 0, 0),  # 5  -- Stop will also ensure that not is running...
            (False, False, True): (0, 0, 0, 0, 0, 0, 0),  # 6
            (False, True, False): (0, 1, 0, 0, 2, 0, 0),  # 7  -- Stop will also ensure that not is running...
            (False, False, False): (0, 0, 0, 0, 0, 0, 0),  # 8
        }

        for running in (True, False):

            def _running(*args: typing.Any, **kwargs: typing.Any) -> bool:
                return running

            for should_try_soft_shutdown in (True, False):
                for execute_later in (True, False):
                    with self.patch_for_worker(
                        is_running=_running,
                        must_stop_before_deletion=True,
                        should_try_soft_shutdown=should_try_soft_shutdown,
                    ) as (instance, _dct):
                        deferred_deleter.DeferredDeletionWorker.add(
                            instance, 'vmid1', execute_later=execute_later
                        )

                        self.assertEqual(
                            COUNTERS_ADD[(running, execute_later, should_try_soft_shutdown)],
                            (
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.STOPPING),
                                instance.is_running.call_count,
                                instance.stop.call_count,
                                instance.shutdown.call_count,
                            ),
                            f'COUNTERS_ADD {running} {execute_later} {should_try_soft_shutdown} --> {COUNTERS_ADD[(running, execute_later, should_try_soft_shutdown)]}',
                        )

                        # Fix last_check
                        self.set_last_check_expired()

                        job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
                        instance.reset_mock()
                        job.run()

                        self.assertEqual(
                            COUNTERS_JOB[(running, execute_later, should_try_soft_shutdown)],
                            (
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP),
                                self.count_entries_on_storage(deferred_types.DeferredStorageGroup.STOPPING),
                                instance.is_running.call_count,
                                instance.stop.call_count,
                                instance.shutdown.call_count,
                            ),
                            f'COUNTERS_JOB {running} {execute_later} {should_try_soft_shutdown} --> {COUNTERS_JOB[(running, execute_later, should_try_soft_shutdown)]}',
                        )

    def test_stop_retry_stop(self) -> None:
        deferred_consts.RETRIES_TO_RETRY = 2
        deferred_consts.MAX_RETRAYABLE_ERROR_RETRIES = 4

        with self.patch_for_worker(
            is_running=helpers.returns_true,
            must_stop_before_deletion=True,
            should_try_soft_shutdown=True,
        ) as (instance, dct):
            deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

            info = next(iter(dct[deferred_types.DeferredStorageGroup.STOPPING].values()))

            self.assertEqual(info.total_retries, 0)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 0)

            instance.is_running.assert_called_once()
            instance.should_try_soft_shutdown.assert_called_once()
            instance.shutdown.assert_called_once()

            instance.reset_mock()

            job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
            # On fist run, will already be running
            self.set_last_check_expired()  # To ensure it's processed
            job.run()

            instance.is_running.assert_called_once()
            instance.reset_mock()

            self.assertEqual(info.total_retries, 1)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 1)

            # On second run, will already be running
            self.set_last_check_expired()
            job.run()

            instance.is_running.assert_called_once()
            instance.reset_mock()

            self.assertEqual(info.total_retries, 2)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 2)

            # On third run, will simply be readded to TO_STOP_GROUP
            self.set_last_check_expired()
            job.run()

            # No calls
            instance.assert_not_called()

            self.assertEqual(info.total_retries, 3)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 3)

            # should be on TO_STOP_GROUP
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP), 1)

            # On next call, again is_running will be called, and stop this time
            self.set_last_check_expired()
            job.run()

            instance.is_running.assert_called_once()
            instance.stop.assert_called_once()
            instance.reset_mock()

            # Reseted retries, but no total_retries (as it's a new try)
            self.assertEqual(info.total_retries, 4)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 0)

            # But sould have been removed from all queues
            # due to MAX_TOTAL_RETRIES, this is checked for every queue on storage access,
            # and STOPPING_GROUP is after TO_STOP_GROUP. So, after STOPPING adds it to TO_DELETE_GROUP
            # the storage access method will remove it from TO_DELETE_GROUP due to MAX_TOTAL_RETRIES
            
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.STOPPING), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)


    def test_delete_retry_delete(self) -> None:
        deferred_consts.RETRIES_TO_RETRY = 2
        deferred_consts.MAX_RETRAYABLE_ERROR_RETRIES = 4

        with self.patch_for_worker(
            is_running=helpers.returns_true,
            is_deleted_side_effect=helpers.returns_false,
        ) as (instance, dct):
            deferred_deleter.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

            info = next(iter(dct[deferred_types.DeferredStorageGroup.DELETING].values()))

            self.assertEqual(info.total_retries, 0)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 0)

            instance.is_running.assert_not_called()
            instance.should_try_soft_shutdown.assert_not_called()
            instance.execute_delete.assert_called()

            instance.reset_mock()

            job = deferred_deleter.DeferredDeletionWorker(environment=mock.MagicMock())
            # On fist run, will already be running
            self.set_last_check_expired()  # To ensure it's processed
            job.run()

            instance.is_deleted.assert_called_once()
            instance.reset_mock()

            self.assertEqual(info.total_retries, 1)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 1)

            # On second run, will already be running
            self.set_last_check_expired()
            job.run()

            instance.is_deleted.assert_called_once()
            instance.reset_mock()

            self.assertEqual(info.total_retries, 2)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 2)

            # On third run, will simply be readded to TO_DELETE_GROUP
            self.set_last_check_expired()
            job.run()

            # No calls
            instance.assert_not_called()

            self.assertEqual(info.total_retries, 3)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 3)

            # should be on TO_DELETE_GROUP
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 1)

            # On next call, again is_running will be called, and stop this time
            self.set_last_check_expired()
            job.run()

            instance.execute_delete.assert_called_once()
            instance.reset_mock()

            # Reseted retries, but no total_retries (as it's a new try)
            self.assertEqual(info.total_retries, 4)
            self.assertEqual(info.fatal_retries, 0)
            self.assertEqual(info.retries, 0)

            # But sould have been removed from all queues
            # due to MAX_TOTAL_RETRIES, this is checked for every queue on storage access,
            # and STOPPING_GROUP is after TO_STOP_GROUP. So, after STOPPING adds it to TO_DELETE_GROUP
            # the storage access method will remove it from TO_DELETE_GROUP due to MAX_TOTAL_RETRIES
            
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_STOP), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.STOPPING), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.TO_DELETE), 0)
            self.assertEqual(self.count_entries_on_storage(deferred_types.DeferredStorageGroup.DELETING), 0)
