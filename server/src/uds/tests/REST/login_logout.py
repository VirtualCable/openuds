import random
import typing


from django.test import TestCase
from django.test.client import Client
from django.conf import settings

from uds.tests import fixtures, tools


class RESTLoginLogoutCase(TestCase):
    """
    Test login and logout
    """

    def setUp(self):
        self.client = tools.getClient()

    def test_login_logout(self):
        """
        Test login and logout
        """
        auth = fixtures.authenticators.createAuthenticator()
        # Create some ramdom users
        admins = fixtures.authenticators.createUsers(
            auth, number_of_users=8, is_admin=True
        )
        stafs = fixtures.authenticators.createUsers(
            auth, number_of_users=8, is_staff=True
        )
        users = fixtures.authenticators.createUsers(auth, number_of_users=8)

        # Create some groups
        groups = fixtures.authenticators.createGroups(auth, number_of_groups=32)

        # Add users to some groups, ramdomly
        for user in users + admins + stafs:
            for group in random.sample(groups, random.randint(1, len(groups))):
                user.groups.add(group)

        # All users, admin and staff must be able to login
        for user in users + admins + stafs:
            response = self.invokeLogin(auth.uuid, user.name, user.name, 200, 'user')
            self.assertEqual(
                response['result'], 'ok', 'Login user {}'.format(user.name)
            )
            self.assertIsNotNone(response['token'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(response['version'], 'Login user {}'.format(user.name))
            self.assertIsNotNone(
                response['scrambler'], 'Login user {}'.format(user.name)
            )

    def invokeLogin(
        self, auth_id: str, username: str, password: str, expectedResponse, what: str
    ) -> typing.Mapping[str, typing.Any]:
        response = self.client.post(
            '/uds/rest/auth/login',
            {
                'auth_id': auth_id,
                'username': username,
                'password': password,
            },
            content_type='application/json',
        )
        self.assertEqual(
            response.status_code, expectedResponse, 'Login {}'.format(what)
        )
        if response.status_code == 200:
            return response.json()

        return {}
