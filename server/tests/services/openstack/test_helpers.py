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

from uds.services.OpenStack import helpers

from . import fixtures

from tests.utils.test import UDSTransactionTestCase
from tests.utils import search_dict_by_attr

#     models.Provider.objects.get(uuid=parameters['prov_uuid']).get_instance(),
# )

# if isinstance(provider, OpenStackProvider):
#     use_subnets_names = provider.use_subnets_name.as_bool()
# else:
#     use_subnets_names = False

# return (provider.api(parameters['project'], parameters['region']), use_subnets_names)


class TestOpenStackHelpers(UDSTransactionTestCase):
    _parameters: dict[str, typing.Any] = {
        'prov_uuid': 'test',
        'project': fixtures.PROJECTS_LIST[0].id,
        'region': fixtures.REGIONS_LIST[0].id,
    }

    def test_get_api(self) -> None:
        # with fixtures.patched_provider() as provider:
        #    pass
        with mock.patch('uds.models.Provider.objects.get') as get_provider:
            helpers.get_api(self._parameters)
            get_provider.assert_called_once_with(uuid=self._parameters['prov_uuid'])

    def test_get_resources(self) -> None:
        with fixtures.patched_provider() as provider:
            with mock.patch('uds.models.Provider.objects.get') as get_provider:
                get_provider.return_value.get_instance.return_value = provider
                result = helpers.list_resources(self._parameters)
                self.assertEqual(len(result), 4)
                # These are all lists
                availability_zone_choices = search_dict_by_attr(result, 'name', 'availability_zone')['choices']
                network_choices = search_dict_by_attr(result, 'name', 'network')['choices']
                flavor_choices = search_dict_by_attr(result, 'name', 'flavor')['choices']
                security_groups_choices = search_dict_by_attr(result, 'name', 'security_groups')['choices']

                self.assertEqual(
                    {(i.id, i.name) for i in fixtures.AVAILABILITY_ZONES_LIST},
                    {(i['id'], i['text']) for i in availability_zone_choices},
                )
                self.assertEqual(
                    {(i.id, i.name) for i in fixtures.NETWORKS_LIST},
                    {(i['id'], i['text']) for i in network_choices},
                )
                self.assertEqual(
                    {i.id for i in fixtures.FLAVORS_LIST if not i.disabled}, {i['id'] for i in flavor_choices}
                )
                self.assertEqual(
                    {(i.name, i.name) for i in fixtures.SECURITY_GROUPS_LIST},
                    {(i['id'], i['text']) for i in security_groups_choices},
                )

    def test_get_volumes(self) -> None:
        with fixtures.patched_provider() as provider:
            with mock.patch('uds.models.Provider.objects.get') as get_provider:
                get_provider.return_value.get_instance.return_value = provider
                result = helpers.list_volumes(self._parameters)
                self.assertEqual(len(result), 1)
                volume_choices = search_dict_by_attr(result, 'name', 'volume')['choices']
                self.assertEqual(
                    {(i.id, i.name) for i in fixtures.VOLUMES_LIST},
                    {(i['id'], i['text']) for i in volume_choices},
                )

    def test_list_servers(self) -> None:
        with fixtures.patched_provider() as provider:
            with mock.patch('uds.models.Provider.objects.get') as get_provider:
                # api = typing.cast(mock.Mock, provider.api)
                get_provider.return_value.get_instance.return_value = provider
                result = helpers.list_servers(self._parameters)
                self.assertEqual(len(result), 1)
                server_choices = search_dict_by_attr(result, 'name', 'machines')['choices']
                self.assertEqual(
                    {(i.id, i.name) for i in fixtures.SERVERS_LIST},
                    {(i['id'], i['text']) for i in server_choices},
                )
