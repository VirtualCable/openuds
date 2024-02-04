# -*- coding: utf-8 -*-

#
# Copyright (c) 2022 Virtual Cable S.L.U.
# All rights reserved.
#

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

# We use commit/rollback

from tests.utils.test import UDSTestCase
from uds.core.util import autoserializable
from uds.core.environment import Environment
from uds.core.managers import crypto

from django.conf import settings


from uds.services.PhysicalMachines import provider, deployment


class IPMachineUserServiceSerializationTest(UDSTestCase):
    def test_marshalling(self):
        obj = deployment.OldIPSerialData()
        obj._ip = '1.1.1.1'
        obj._state = 'state'
        obj._reason = 'reason'

        def _check_fields(instance: deployment.IPMachineUserService) -> None:
            self.assertEqual(instance._ip, '1.1.1.1')
            self.assertEqual(instance._state, 'state')
            self.assertEqual(instance._reason, 'reason')

        data = obj.marshal()

        instance = deployment.IPMachineUserService(environment=Environment.testing_environment(), service=None)
        instance.unmarshal(data)

        marshaled_data = instance.marshal()

        # Ensure remarshalled flag is set
        self.assertTrue(instance.needs_upgrade())
        instance.mark_for_upgrade(False)  # reset flag

        # Ensure fields has been marshalled using new format
        self.assertTrue(autoserializable.is_autoserializable_data(marshaled_data))

        # Check fields
        _check_fields(instance)

        # Reunmarshall again and check that remarshalled flag is not set
        instance = deployment.IPMachineUserService(environment=Environment.testing_environment(), service=None)
        instance.unmarshal(marshaled_data)
        self.assertFalse(instance.needs_upgrade())

        # Check fields again
        _check_fields(instance)
