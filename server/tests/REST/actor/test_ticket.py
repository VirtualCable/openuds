# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import logging
import typing

from uds import models

from ...utils import rest
from ...fixtures import servers as servers_fixtures, services as services_fixtures

if typing.TYPE_CHECKING:
    from uds import models


logger = logging.getLogger(__name__)


class ActorTestTicket(rest.test.RESTActorTestCase):
    """
    Test actor functionality for ticket generation
    """

    server: 'models.Server'
    userservice: 'models.UserService'

    def setUp(self) -> None:
        super().setUp()
        # Create a Server for testing
        # Will be cleaned up on test end
        self.server = servers_fixtures.create_server()
        provider = services_fixtures.create_db_provider()
        service = services_fixtures.create_db_service(provider)
        servicepool = services_fixtures.create_db_servicepool(service)
        publication = services_fixtures.create_db_publication(servicepool)
        self.userservice = services_fixtures.create_db_userservice(servicepool, publication)

    def test_valid_ticket_from_server(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        token = self.login_and_register()
        data = {'field1': 'fld1', 'field2': 'fld2'}
        ticket = models.TicketStore.create(data=data)

        response = self.client.post(
            '/uds/rest/actor/v3/ticket',
            data={'token': token, 'ticket': ticket},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], data)

    def test_invalid_token_from_server(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        data = {'field1': 'fld1', 'field2': 'fld2'}
        ticket = models.TicketStore.create(data=data)

        response = self.client.post(
            '/uds/rest/actor/v3/ticket',
            data={'token': 'invalid', 'ticket': ticket},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)  # Forbidden
        self.assertIsInstance(response.json()['error'], str)

    def test_invalid_ticket_from_server(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        token = self.login_and_register()
        response = self.client.post(
            '/uds/rest/actor/v3/ticket',
            data={'token': token, 'ticket': 'invalid'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)  # Forbidden
        self.assertIsInstance(response.json()['error'], str)

    def test_valid_ticket_from_userservice(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        token = self.userservice.uuid
        data = {'field1': 'fld1', 'field2': 'fld2'}
        ticket = models.TicketStore.create(owner=token, data=data)

        response = self.client.post(
            '/uds/rest/actor/v3/ticket/userservice',
            data={'token': token, 'ticket': ticket},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], data)

    def test_invalid_token_from_userservice(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        token = self.userservice.uuid
        data = {'field1': 'fld1', 'field2': 'fld2'}
        ticket = models.TicketStore.create(owner=token, data=data)

        response = self.client.post(
            '/uds/rest/actor/v3/ticket/userservice',
            data={'token': 'invalid', 'ticket': ticket},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)  # Forbidden
        self.assertIsInstance(response.json()['error'], str)
        
    def test_invalid_ticket_from_userservice(self) -> None:
        """
        Test actorv3 ticket generation from a server request
        """
        token = self.userservice.uuid
        response = self.client.post(
            '/uds/rest/actor/v3/ticket/userservice',
            data={'token': token, 'ticket': 'invalid'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)  # Forbidden
        self.assertIsInstance(response.json()['error'], str)