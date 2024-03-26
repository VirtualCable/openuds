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
import random
from unittest import mock

from uds import models
from uds.core import types, environment

from . import fixtures

from ...utils.test import UDSTransactionTestCase

from uds.services.OpenStack.provider import OpenStackProvider
from uds.services.OpenStack.provider_legacy import OpenStackProviderLegacy


class TestOpenstackProvider(UDSTransactionTestCase):
    def test_provider(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider() as provider:
            api = typing.cast(mock.MagicMock, provider.api())

            self.assertEqual(provider.test_connection(), types.core.TestResult(True, mock.ANY))
            # Ensure test_connection is called
            api.test_connection.assert_called_once()

            self.assertEqual(provider.is_available(), True)
            api.is_available.assert_called_once()

            # Clear mock calls
            api.reset_mock()
            OpenStackProvider.test(
                env=environment.Environment.testing_environment(), data=fixtures.PROVIDER_VALUES_DICT
            )

    def test_provider_legacy(self) -> None:
        """
        Test the provider
        """
        with fixtures.patched_provider_legacy() as provider:
            api = typing.cast(mock.MagicMock, provider.api())

            self.assertEqual(provider.test_connection(), types.core.TestResult(True, mock.ANY))
            # Ensure test_connection is called
            api.test_connection.assert_called_once()

            self.assertEqual(provider.is_available(), True)
            api.is_available.assert_called_once()

            # Clear mock calls
            api.reset_mock()
            OpenStackProviderLegacy.test(
                env=environment.Environment.testing_environment(), data=fixtures.PROVIDER_VALUES_DICT
            )

    def test_helpers(self) -> None:
        """
        Test the Helpers. In fact, not used on provider, but on services (fixed, live, ...)
        """
        from uds.services.OpenStack.helpers import get_machines, get_resources, get_volumes

        for patcher in (fixtures.patched_provider, fixtures.patched_provider_legacy):
            with patcher() as prov:
                # Ensure exists on db
                db_provider = models.Provider.objects.create(
                    name='test proxmox provider',
                    comments='test comments',
                    data_type=prov.type_type,
                    data=prov.serialize(),
                )

                parameters: dict[str, str] = {
                    'prov_uuid': db_provider.uuid,
                    'project': random.choice(fixtures.PROJECTS_LIST).id,
                    'region': random.choice(fixtures.REGIONS_LIST).id,
                }
                # Test get_storage
                # Helpers need a bit more patching to work
                # We must patch get_api(parameters: dict[str, str]) -> tuple[openstack_client.OpenstackClient, bool]:
                with mock.patch('uds.services.OpenStack.helpers.get_api') as get_api:
                    get_api.return_value = (prov.api(), False)
                    
                    h_machines = get_machines(parameters)
                    self.assertEqual(len(h_machines), 1)
                    self.assertEqual(h_machines[0]['name'], 'machines')
                    self.assertEqual(sorted(i['id'] for i in h_machines[0]['choices']), sorted(i.id for i in fixtures.SERVERS_LIST))
                    
                    h_resources = get_resources(parameters)
                    # [{'name': 'availability_zone', 'choices': [...]}, {'name': 'network', 'choices': [...]}, {'name': 'flavor', 'choices': [...]}, {'name': 'security_groups', 'choices': [...]}]
                    self.assertEqual(len(h_resources), 4)
                    self.assertEqual(sorted(i['name'] for i in h_resources), ['availability_zone', 'flavor', 'network', 'security_groups'])
                    def _get_choices_for(name: str) -> list[str]:
                        return [i['id'] for i in next(i for i in h_resources if i['name'] == name)['choices']]
                    
                    self.assertEqual(sorted(_get_choices_for('availability_zone')), sorted(i.id for i in fixtures.AVAILABILITY_ZONES_LIST))
                    self.assertEqual(sorted(_get_choices_for('network')), sorted(i.id for i in fixtures.NETWORKS_LIST))
                    self.assertEqual(sorted(_get_choices_for('flavor')), sorted(i.id for i in fixtures.FLAVORS_LIST if not i.disabled))
                    self.assertEqual(sorted(_get_choices_for('security_groups')), sorted(i.id for i in fixtures.SECURITY_GROUPS_LIST))
                    
                    # [{'name': 'volume', 'choices': [...]}]
                    h_volumes = get_volumes(parameters)
                    self.assertEqual(len(h_volumes), 1)
                    self.assertEqual(h_volumes[0]['name'], 'volume')
                    self.assertEqual(sorted(i['id'] for i in h_volumes[0]['choices']), sorted(i.id for i in fixtures.VOLUMES_LIST))
