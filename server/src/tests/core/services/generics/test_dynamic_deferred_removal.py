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
from uds.core.workers import deferred_deletion
from uds.core.services.generics import exceptions as gen_exceptions

from ....utils.test import UDSTransactionTestCase
from . import fixtures


class DynamicServiceTest(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()

        services.factory().insert(fixtures.DynamicTestingProvider)

    def set_last_check_expired(self) -> None:
        for group in [deferred_deletion.TO_DELETE_GROUP, deferred_deletion.DELETING_GROUP]:
            with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(group) as storage:
                for key, info in typing.cast(
                    dict[str, deferred_deletion.DeferredDeletionInfo], storage
                ).items():
                    info.last_check = sql_now() - datetime.timedelta(
                        seconds=deferred_deletion.CHECK_INTERVAL * 2
                    )
                    storage[key] = info

    def count_entries_on_storage(self, group: str) -> int:
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(group) as storage:
            return len(storage)

    @contextlib.contextmanager
    def patch_for_worker(
        self,
        group: str,
        execute_side_effect: typing.Union[None, typing.Callable[..., None], Exception] = None,
        is_deleted_side_effect: typing.Union[None, typing.Callable[..., bool], Exception] = None,
    ) -> typing.Iterator[tuple[mock.MagicMock, dict[str, dict[str, deferred_deletion.DeferredDeletionInfo]]]]:
        """
        Patch the storage to use a dict instead of the real storage

        This is useful to test the worker without touching the real storage
        """
        dct: dict[str, dict[str, deferred_deletion.DeferredDeletionInfo]] = {}
        instance = mock.MagicMock()
        instance_db_obj = mock.MagicMock(uuid='service1')
        instance_db_obj.get_instance.return_value = instance
        instance.db_obj.return_value = instance_db_obj
        instance.execute_delete.side_effect = execute_side_effect
        if is_deleted_side_effect == None:
            instance.is_deleted.return_value = True
        else:
            instance.is_deleted.side_effect = is_deleted_side_effect

        # Patchs uds.models.Service also for get_instance to work
        with mock.patch('uds.models.Service.objects') as objs:
            objs.get.return_value = instance.db_obj()
            with mock.patch(
                'uds.core.workers.deferred_deletion.DeferredDeletionWorker.deferred_storage'
            ) as storage:

                @contextlib.contextmanager
                def _as_dict(
                    group: str, *args: typing.Any, **kwargs: typing.Any
                ) -> typing.Iterator[dict[str, deferred_deletion.DeferredDeletionInfo]]:
                    if group not in dct:
                        dct[group] = {}
                    yield dct[group]

                storage.as_dict.side_effect = _as_dict
                yield instance, dct

    def test_deferred_delete_full_fine_delete(self) -> None:

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
            instance.delete(mock.MagicMock(), f'vmid_{count}')
            instance.mock.execute_delete.assert_called_with(f'vmid_{count}')

        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.execute_delete.call_count, 8)
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.is_deleted.call_count, 0)
        # Reset mock
        fixtures.DynamicTestingServiceForDeferredDeletion.mock.reset_mock()

        # No entries to_delete
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)

        # Storage db should have 8 entries
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.DELETING_GROUP
        ) as deleting:
            self.assertEqual(len(deleting), 8)
            for key, info in typing.cast(dict[str, deferred_deletion.DeferredDeletionInfo], deleting).items():
                now = sql_now()
                self.assertIsInstance(info, deferred_deletion.DeferredDeletionInfo)
                self.assertEqual(key, f'{info.service_uuid}_{info.vmid}')
                self.assertLessEqual(info.created, now)
                self.assertLessEqual(info.last_check, now)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 0)

        # Instantiate the Job
        job = deferred_deletion.DeferredDeletionWorker(environment=mock.MagicMock())
        to_delete = job._get_from_storage(deferred_deletion.TO_DELETE_GROUP)
        # Should be empty, both services and infos
        self.assertEqual(len(to_delete[0]), 0)
        self.assertEqual(len(to_delete[1]), 0)

        # Now, get from deleting
        deleting = job._get_from_storage(deferred_deletion.DELETING_GROUP)
        # Should have o services and infos also, because last_check has been too soon
        self.assertEqual(len(deleting[0]), 0)
        self.assertEqual(len(deleting[1]), 0)

        # Update last_check for all entries and recheck
        self.set_last_check_expired()

        # Now, get from deleting again, should have all services and infos
        # OVerride MAX_DELETIONS_AT_ONCE to get only 4 entries
        deferred_deletion.MAX_DELETIONS_AT_ONCE = 4
        services_1, key_info_1 = job._get_from_storage(deferred_deletion.DELETING_GROUP)
        self.assertEqual(len(services_1), 4)
        self.assertEqual(len(key_info_1), 4)
        # And should rest only 4 on storage
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.DELETING_GROUP
        ) as deleting:
            self.assertEqual(len(deleting), 4)
        # again, should return 4 entries
        services_2, key_info_2 = job._get_from_storage(deferred_deletion.DELETING_GROUP)
        self.assertEqual(len(services_2), 4)
        self.assertEqual(len(key_info_2), 4)

        # Re-store all DELETING_GROUP entries
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.DELETING_GROUP
        ) as deleting:
            for info in itertools.chain(key_info_1, key_info_2):
                deleting[info[0]] = info[1]

        # set MAX_DELETIONS_AT_ONCE to a value bigger than 8
        deferred_deletion.MAX_DELETIONS_AT_ONCE = 9

        # Now, process all entries normally
        job.run()

        # Should have called is_deleted 8 times
        self.assertEqual(fixtures.DynamicTestingServiceForDeferredDeletion.mock.is_deleted.call_count, 8)
        # And should have removed all entries from deleting, because is_deleted returns True
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.DELETING_GROUP
        ) as deleting:
            self.assertEqual(len(deleting), 0)

    def test_deferred_delete_delayed_full(self) -> None:
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
        deferred_deletion.DeferredDeletionWorker.add(instance, 'vmid_1', execute_later=True)
        instance.mock.execute_delete.assert_not_called()

        # No entries deleting
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
        # to_delete should contain one entry
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 1)

        job = deferred_deletion.DeferredDeletionWorker(environment=mock.MagicMock())
        to_delete = job._get_from_storage(deferred_deletion.TO_DELETE_GROUP)
        # Should be empty, both services and infos
        self.assertEqual(len(to_delete[0]), 0)
        self.assertEqual(len(to_delete[1]), 0)

        # Update the last_check for the entry and recheck
        self.set_last_check_expired()

        # Now, get from deleting again, should have all services and infos
        services, key_info = job._get_from_storage(deferred_deletion.TO_DELETE_GROUP)
        self.assertEqual(len(services), 1)
        self.assertEqual(len(key_info), 1)
        # now, db should be empty
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)

        # Re store the entry
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.TO_DELETE_GROUP
        ) as to_delete:
            for info in key_info:
                to_delete[info[0]] = info[1]

        # Process should move from to_delete to deleting
        job.run()  # process_to_delete and process_deleting

        # Should have called execute_delete once
        instance.mock.execute_delete.assert_called_once_with('vmid_1')
        # And should have removed all entries from to_delete
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 1)

        instance.mock.reset_mock()
        # And should have one entry in deleting
        with deferred_deletion.DeferredDeletionWorker.deferred_storage.as_dict(
            deferred_deletion.DELETING_GROUP
        ) as deleting:
            self.assertEqual(len(deleting), 1)
            for key, info in typing.cast(dict[str, deferred_deletion.DeferredDeletionInfo], deleting).items():
                now = sql_now()
                self.assertIsInstance(info, deferred_deletion.DeferredDeletionInfo)
                self.assertEqual(key, f'{info.service_uuid}_{info.vmid}')
                self.assertLessEqual(info.created, now)
                self.assertLessEqual(info.last_check, now)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 0)

        # And no call to is_deleted
        instance.mock.is_deleted.assert_not_called()

        # Executing now, should do nothing because last_check is not expired
        job.run()

        # Should have called is_deleted 0 times, due to last_check not expired
        instance.mock.is_deleted.assert_not_called()

        self.set_last_check_expired()  # So deleting gets processed

        job.run()

        # Now should have called is_deleted once, and no entries in deleting nor to_delete
        instance.mock.is_deleted.assert_called_once_with('vmid_1')
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
        self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)

    def test_deferred_deletion_fails_add(self) -> None:
        for error in (
            gen_exceptions.RetryableError('error'),
            gen_exceptions.NotFoundError('error'),
            gen_exceptions.FatalError('error'),
        ):
            with self.patch_for_worker(
                deferred_deletion.TO_DELETE_GROUP,
                execute_side_effect=error,
            ) as (instance, dct):
                deferred_deletion.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

                # Not found should remove the entry and nothing more
                if isinstance(error, gen_exceptions.NotFoundError):
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
                    continue

                self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 1)
                self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)

                info = next(iter(dct[deferred_deletion.TO_DELETE_GROUP].values()))  # Get first element
                self.assertEqual(info.vmid, 'vmid1')
                self.assertEqual(info.service_uuid, instance.db_obj().uuid)
                self.assertEqual(info.fatal_retries, 0)
                self.assertEqual(info.total_retries, 0)  # On adding & error, no count is increased

                job = deferred_deletion.DeferredDeletionWorker(environment=mock.MagicMock())
                job.run()
                # due to check_interval, no retries are done
                self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 1)
                self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)

                # Fix last_check
                self.set_last_check_expired()

                # And run again
                job.run()

                if isinstance(error, gen_exceptions.RetryableError):
                    self.assertEqual(info.fatal_retries, 0)
                    self.assertEqual(info.total_retries, 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
                    # Test that MAX_TOTAL_RETRIES works fine
                    deferred_deletion.MAX_TOTAL_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
                else:
                    self.assertEqual(info.fatal_retries, 1)
                    self.assertEqual(info.total_retries, 1)
                    # test that MAX_FATAL_RETRIES works fine
                    deferred_deletion.MAX_FATAL_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)

    def test_deferred_deletion_fails_is_deleted(self) -> None:
        for error in (
            gen_exceptions.RetryableError('error'),
            gen_exceptions.NotFoundError('error'),
            gen_exceptions.FatalError('error'),
        ):
            with self.patch_for_worker(
                deferred_deletion.DELETING_GROUP,
                is_deleted_side_effect=error,
            ) as (instance, dct):
                deferred_deletion.DeferredDeletionWorker.add(instance, 'vmid1', execute_later=False)

                # No entries in TO_DELETE_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                # One entry in DELETING_GROUP
                self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 1)

                info = next(iter(dct[deferred_deletion.DELETING_GROUP].values()))

                # Fix last_check
                self.set_last_check_expired()

                job = deferred_deletion.DeferredDeletionWorker(environment=mock.MagicMock())
                job.run()

                # Should have called is_deleted once

                if isinstance(error, gen_exceptions.RetryableError):
                    self.assertEqual(info.fatal_retries, 0)
                    self.assertEqual(info.total_retries, 1)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 1)
                    # Test that MAX_TOTAL_RETRIES works fine
                    deferred_deletion.MAX_TOTAL_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
                elif isinstance(error, gen_exceptions.NotFoundError):
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
                else:
                    self.assertEqual(info.fatal_retries, 1)
                    self.assertEqual(info.total_retries, 1)
                    # test that MAX_FATAL_RETRIES works fine
                    deferred_deletion.MAX_FATAL_ERROR_RETRIES = 2
                    # reset last_check, or it will not retry
                    self.set_last_check_expired()
                    job.run()
                    # Should have removed the entry
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.TO_DELETE_GROUP), 0)
                    self.assertEqual(self.count_entries_on_storage(deferred_deletion.DELETING_GROUP), 0)
