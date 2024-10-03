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
from unittest import mock

from uds.services.Proxmox import helpers

from . import fixtures

from ...utils.test import UDSTransactionTestCase


class TestProxmoxHelpers(UDSTransactionTestCase):
    _parameters: dict[str, typing.Any] = {
        'prov_uuid': 'test',
        'machine': fixtures.VMINFO_LIST[0].id,  # Used on get_storage
        'pool': fixtures.POOLS[0].id,  # Used on get_machines
    }

    def test_get_provider(self) -> None:
        # with fixtures.patched_provider() as provider:
        #    pass
        with mock.patch('uds.models.Provider.objects.get') as get_provider:
            helpers.get_provider(self._parameters)
            get_provider.assert_called_once_with(uuid=self._parameters['prov_uuid'])

    def test_get_storage(self) -> None:
        with fixtures.patched_provider() as provider:
            with mock.patch('uds.models.Provider.objects.get') as get_provider:
                api = typing.cast(mock.Mock, provider.api)
                get_provider.return_value.get_instance.return_value = provider
                result = helpers.get_storage(self._parameters)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], 'datastore')
                choices = result[0]['choices']
                self.assertIsInstance(choices, list)
                self.assertGreaterEqual(len(choices), 1)
                for choice in choices:
                    self.assertIsInstance(choice, dict)
                    self.assertIsInstance(choice['id'], str)
                    self.assertIsInstance(choice['text'], str)

                api.get_vm_info.assert_called_once()
                api.list_storages.assert_called_once()

    def test_get_machines(self) -> None:
        with fixtures.patched_provider() as provider:
            with mock.patch('uds.models.Provider.objects.get') as get_provider:
                api = typing.cast(mock.Mock, provider.api)
                get_provider.return_value.get_instance.return_value = provider
                result = helpers.get_machines(self._parameters)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], 'machines')
                choices = result[0]['choices']
                self.assertIsInstance(choices, list)
                self.assertGreaterEqual(len(choices), 1)
                for choice in choices:
                    self.assertIsInstance(choice, dict)
                    self.assertIsInstance(choice['id'], str)
                    self.assertIsInstance(choice['text'], str)

                api.get_pool_info.assert_called_once()
