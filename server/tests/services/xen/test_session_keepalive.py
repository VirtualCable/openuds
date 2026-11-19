#
# Copyright (c) 2024 Virtual Cable S.L.
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
Author: Andres Schumann, aschumann at virtualcable dot es
"""

import threading
import typing
import unittest

import XenAPI

from uds.services.Xen.xen import client as xen_client
from uds.services.Xen.xen import exceptions as xen_exceptions

from . import fixtures


class _FakeClient:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset_session(self) -> None:
        self.reset_calls += 1

    @xen_exceptions.catched
    def call_with_session_failure(self) -> None:
        raise XenAPI.Failure(["HANDLE_INVALID", "session", "OpaqueRef:session-1"])

    @xen_exceptions.catched
    def call_with_vm_failure(self) -> None:
        raise XenAPI.Failure(["HANDLE_INVALID", "VM", "OpaqueRef:vm-1"])


class _Pool:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def get_all(self) -> list[str]:
        if self.error is not None:
            raise self.error
        return []


class _LoggedInClient:
    def __init__(self, pool_error: Exception | None = None) -> None:
        self._logged_in = True
        self._pool = _Pool(pool_error)
        self.logins = 0
        self.resets = 0

    def _get_xenapi_property(self, prop: str) -> typing.Any:
        return self._pool

    def login(
        self, switch_to_master: bool = False, backup_checked: bool = False
    ) -> None:
        self.logins += 1
        self._logged_in = True

    def reset_session(self) -> None:
        self.resets += 1
        self._logged_in = False


class TestXenSessionKeepAlive(unittest.TestCase):
    def test_leaving_get_connection_keeps_the_session_open(self) -> None:
        provider = fixtures.create_provider()
        client = fixtures.create_client_mock()
        provider._cached_api = client

        with provider.get_connection() as conn:
            self.assertIs(conn, client)

        client.logout.assert_not_called()
        self.assertIs(provider.api, client)

    def test_connection_check_uses_the_shared_session_under_the_lock(self) -> None:
        provider = fixtures.create_provider()
        client = fixtures.create_client_mock()
        provider._cached_api = client

        provider.test_connection()

        client.test.assert_called_once_with()
        client.logout.assert_not_called()

    def test_initialize_drops_the_previous_client_without_calling_the_server(
        self,
    ) -> None:
        provider = fixtures.create_provider()
        client = fixtures.create_client_mock()
        provider._cached_api = client

        provider.initialize(None)

        client.logout.assert_not_called()
        self.assertIsNone(provider._cached_api)

    def test_expired_session_is_retryable_and_resets_the_client(self) -> None:
        client = _FakeClient()

        with self.assertRaises(xen_exceptions.XenSessionExpired) as ctx:
            client.call_with_session_failure()

        self.assertIsInstance(ctx.exception, xen_exceptions.XenRetryableError)
        self.assertEqual(client.reset_calls, 1)

    def test_invalid_vm_handle_is_not_a_session_expiry(self) -> None:
        client = _FakeClient()

        with self.assertRaises(xen_exceptions.XenNotFoundError):
            client.call_with_vm_failure()

        self.assertEqual(client.reset_calls, 0)

    def test_task_info_session_expiry_resets_the_client(self) -> None:
        class _Tasks:
            def get_record(self, ref: str) -> None:
                raise XenAPI.Failure(
                    ["HANDLE_INVALID", "session", "OpaqueRef:session-1"]
                )

        class _Client:
            def __init__(self) -> None:
                self.reset_calls = 0
                self.task = _Tasks()

            def reset_session(self) -> None:
                self.reset_calls += 1

        fake = _Client()

        with self.assertRaises(xen_exceptions.XenSessionExpired):
            xen_client.XenClient.get_task_info(
                typing.cast(typing.Any, fake), "OpaqueRef:task-1"
            )

        self.assertEqual(fake.reset_calls, 1)

    def test_live_session_is_checked_on_the_server_without_logging_in(self) -> None:
        client = _LoggedInClient()

        xen_client.XenClient.test(typing.cast(typing.Any, client))

        self.assertEqual(client.logins, 0)
        self.assertEqual(client.resets, 0)

    def test_expired_session_on_check_is_replaced_by_a_new_login(self) -> None:
        expired = XenAPI.Failure(["HANDLE_INVALID", "session", "OpaqueRef:session-1"])
        client = _LoggedInClient(pool_error=expired)

        xen_client.XenClient.test(typing.cast(typing.Any, client))

        self.assertEqual(client.resets, 1)
        self.assertEqual(client.logins, 1)

    def test_unreachable_server_fails_the_check_and_does_not_log_in(self) -> None:
        client = _LoggedInClient(pool_error=ConnectionError("server down"))

        with self.assertRaises(xen_exceptions.XenException):
            xen_client.XenClient.test(typing.cast(typing.Any, client))

        self.assertEqual(client.logins, 0)

    def test_concurrent_connections_are_serialized(self) -> None:
        provider = fixtures.create_provider()
        provider._cached_api = fixtures.create_client_mock()
        inside = threading.Event()
        release = threading.Event()
        order: list[str] = []

        def first() -> None:
            with provider.get_connection():
                order.append("first-in")
                inside.set()
                release.wait(5)
                order.append("first-out")

        def second() -> None:
            inside.wait(5)
            with provider.get_connection():
                order.append("second-in")

        t1 = threading.Thread(target=first)
        t2 = threading.Thread(target=second)
        t1.start()
        t2.start()
        inside.wait(5)
        release.set()
        t1.join(5)
        t2.join(5)

        self.assertEqual(order, ["first-in", "first-out", "second-in"])
