# -*- coding: utf-8 -*-
"""
Unit tests for OpenshiftService logic.
All tests use fixtures for setup and mock dependencies.
Tests are grouped by functionality: configuration, utility methods, availability, VM operations, exception handling, and deletion.
"""

#
# Copyright (c) 2024 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
Reorganizado y corregido por GitHub Copilot
"""

import typing
from unittest import mock
from uds.services.OpenShift.openshift import exceptions as morph_exceptions

from tests.services.openshift import fixtures
from tests.utils.test import UDSTransactionTestCase


class TestOpenshiftService(UDSTransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        fixtures.clear()

    def _create_service_with_provider(self):
        """
        Helper to create a service with a patched provider.
        """
        provider_ctx = fixtures.patched_provider()
        provider = provider_ctx.__enter__()
        service = fixtures.create_service(provider=provider)
        return service, provider, provider_ctx

    # --- Configuration and initial data ---
    def test_service_data(self) -> None:
        """
        Check initial service data values.
        """
        service = fixtures.create_service()
        self.assertEqual(service.template.value, fixtures.SERVICE_VALUES_DICT['template'])
        self.assertEqual(service.basename.value, fixtures.SERVICE_VALUES_DICT['basename'])
        self.assertEqual(service.lenname.value, fixtures.SERVICE_VALUES_DICT['lenname'])
        self.assertEqual(service.publication_timeout.value, fixtures.SERVICE_VALUES_DICT['publication_timeout'])

    def test_initialize_sets_basename(self) -> None:
        """
        Check that initialize sets basename and lenname correctly.
        """
        service = fixtures.create_service()
        service.basename.value = 'testname'
        service.lenname.value = 6
        service.initialize({'basename': 'testname', 'lenname': 6})
        self.assertEqual(service.basename.value, 'testname')
        self.assertEqual(service.lenname.value, 6)

    def test_init_gui_sets_choices(self) -> None:
        """
        Check that init_gui sets template choices.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        with mock.patch.object(service.template, 'set_choices') as set_choices_mock:
            service.init_gui()
            set_choices_mock.assert_called()
        provider_ctx.__exit__(None, None, None)

    # --- Utility and accessor methods ---
    def test_provider_returns_correct_type(self) -> None:
        """
        Check that provider() returns the correct provider instance.
        """
        service, provider, provider_ctx = self._create_service_with_provider()
        self.assertEqual(service.provider(), provider)
        provider_ctx.__exit__(None, None, None)

    def test_api_property_caching(self) -> None:
        """
        Check that the api property is cached.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        api1 = service.api
        api2 = service.api
        self.assertIs(api1, api2)
        provider_ctx.__exit__(None, None, None)

    def test_service_methods(self) -> None:
        """
        Check utility methods of the service.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        self.assertEqual(service.get_basename(), service.basename.value)
        self.assertEqual(service.get_lenname(), service.lenname.value)
        self.assertEqual(service.sanitized_name('Test VM 1'), 'test-vm-1')
        duplicates = list(service.find_duplicates('vm-1', '00:11:22:33:44:55'))
        self.assertEqual(len(duplicates), 1)
        provider_ctx.__exit__(None, None, None)

    # --- Availability and cache ---
    def test_service_is_available(self) -> None:
        """
        Check service availability and cache handling.
        """
        service, provider, provider_ctx = self._create_service_with_provider()
        api = typing.cast(mock.MagicMock, provider.api)
        self.assertTrue(service.is_available())
        api.test.assert_called_with()
        api.test.return_value = False
        self.assertTrue(service.is_available())
        service.provider().is_available.cache_clear()  # type: ignore
        self.assertFalse(service.is_available())
        api.test.assert_called_with()
        provider_ctx.__exit__(None, None, None)

    # --- VM operations ---
    def test_vm_operations(self) -> None:
        """
        Check VM operations: get_ip, get_mac, is_running, start, stop, shutdown.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        api = typing.cast(mock.MagicMock, service.api)
        ip = service.get_ip(None, 'vm-1')
        self.assertEqual(ip, '192.168.1.1')
        mac = service.get_mac(None, 'vm-1')
        self.assertEqual(mac, '00:11:22:33:44:01')
        self.assertTrue(service.is_running(None, 'vm-1'))
        service.start(None, 'vm-1')
        api.start_vm_instance.assert_called_with('vm-1')
        service.stop(None, 'vm-1')
        api.stop_vm_instance.assert_called_with('vm-1')
        service.shutdown(None, 'vm-1')
        api.stop_vm_instance.assert_called_with('vm-1')
        provider_ctx.__exit__(None, None, None)

    # --- Exception handling ---
    def test_get_ip_raises_exception_if_no_interfaces(self) -> None:
        """
        Check that get_ip raises an exception if there are no interfaces.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        def no_interfaces(_vmid: str):
            mock_vm = mock.Mock()
            mock_vm.interfaces = []
            return mock_vm
        with mock.patch.object(service.api, 'get_vm_instance_info', side_effect=no_interfaces):
            with self.assertRaises(Exception):
                service.get_ip(None, 'vm-1')
        provider_ctx.__exit__(None, None, None)

    def test_get_mac_raises_exception_if_no_interfaces(self) -> None:
        """
        Check that get_mac raises an exception if there are no interfaces.
        """
        service, _, provider_ctx = self._create_service_with_provider()
        def no_interfaces(_vmid: str):
            mock_vm = mock.Mock()
            mock_vm.interfaces = []
            return mock_vm
        with mock.patch.object(service.api, 'get_vm_instance_info', side_effect=no_interfaces):
            with self.assertRaises(Exception):
                service.get_mac(None, 'vm-1')
        provider_ctx.__exit__(None, None, None)

    # --- VM deletion ---
    def test_vm_deletion(self) -> None:
        """
        Check VM deletion logic and is_deleted method.
        """
        service, provider, provider_ctx = self._create_service_with_provider()
        api = typing.cast(mock.MagicMock, provider.api)

        # Execute deletion
        service.execute_delete('vm-1')
        api.delete_vm_instance.assert_called_with('vm-1')

        # Check if deleted
        api.get_vm_info.side_effect = morph_exceptions.OpenshiftNotFoundError('not found')
        self.assertTrue(service.is_deleted('vm-1'))

        # Simulate VM exists
        api.get_vm_info.side_effect = None
        api.get_vm_info.return_value = fixtures.VMS[0]
        self.assertFalse(service.is_deleted('vm-1'))
        provider_ctx.__exit__(None, None, None)