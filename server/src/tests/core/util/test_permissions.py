# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

from uds.core.util import permissions
from uds.core.util import ot
from uds import models

from ...utils.test import UDSTransactionTestCase
from ...fixtures import authenticators as authenticators_fixtures, services as services_fixtures


class PermissionsTests(UDSTransactionTestCase):
    authenticator: models.Authenticator
    groups: typing.List[models.Group]
    users: typing.List[models.User]
    admins: typing.List[models.User]
    staffs: typing.List[models.User]
    userService: models.UserService

    def setUp(self) -> None:
        self.authenticator = authenticators_fixtures.createAuthenticator()
        self.groups = authenticators_fixtures.createGroups(self.authenticator)
        self.users = authenticators_fixtures.createUsers(self.authenticator, groups=self.groups)
        self.admins = authenticators_fixtures.createUsers(self.authenticator, is_admin=True, groups=self.groups)
        self.staffs = authenticators_fixtures.createUsers(self.authenticator, is_staff=True, groups=self.groups)
        self.userService = services_fixtures.createSingleTestingUserServiceStructure(services_fixtures.createProvider(), self.users[0], list(self.users[0].groups.all()), 'managed')

    def doTestUserPermissions(self, obj, user: models.User):
        permissions.addUserPermission(user, obj, permissions.PERMISSION_NONE)
        self.assertEquals(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_NONE)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ), user.is_admin)
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_MANAGEMENT), user.is_admin)
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL), user.is_admin)

        # Add a new permission, must overwrite the previous one
        permissions.addUserPermission(user, obj, permissions.PERMISSION_ALL)
        self.assertEquals(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_ALL)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_MANAGEMENT))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL))

        # Again, with read
        permissions.addUserPermission(user, obj, permissions.PERMISSION_READ)
        self.assertEquals(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_READ)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ))
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_MANAGEMENT), user.is_admin)
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL), user.is_admin)

        # Remove obj, permissions must have gone away
        obj.delete()
        self.assertEquals(models.Permissions.objects.count(), 0)

    def doTestGroupPermissions(self, obj, user: models.User):
        group = user.groups.all()[0]

        permissions.addGroupPermission(group, obj, permissions.PERMISSION_NONE)
        self.assertEquals(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_NONE)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        # Admins has all permissions ALWAYS
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ), user.is_admin)
        self.assertEqual(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL), user.is_admin)
            

        permissions.addGroupPermission(group, obj, permissions.PERMISSION_ALL)
        self.assertEquals(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_ALL)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL))

        # Add user permission, DB must contain both an return ALL

        permissions.addUserPermission(user, obj, permissions.PERMISSION_READ)
        self.assertEquals(models.Permissions.objects.count(), 2)
        perm = models.Permissions.objects.all()[0]
        self.assertEquals(perm.object_type, ot.getObjectType(obj))
        self.assertEquals(perm.object_id, obj.pk)
        self.assertEquals(perm.permission, permissions.PERMISSION_ALL)
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_NONE))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_READ))
        self.assertTrue(permissions.checkPermissions(user, obj, permissions.PERMISSION_ALL))

        # Remove obj, permissions must have gone away
        obj.delete()
        self.assertEquals(models.Permissions.objects.count(), 0)

    # Every tests reverses the DB and recalls setUp

    def test_user_auth_permissions_user(self):
        self.doTestUserPermissions(self.authenticator, self.users[0])

    def test_user_auth_permissions_admin(self):
        self.doTestUserPermissions(self.authenticator, self.admins[0])

    def test_user_auth_permissions_staff(self):
        self.doTestUserPermissions(self.authenticator, self.staffs[0])

    def test_group_auth_permissions_user(self):
        self.doTestGroupPermissions(self.authenticator, self.users[0])

    def test_group_auth_permissions_admin(self):
        self.doTestGroupPermissions(self.authenticator, self.admins[0])

    def test_group_auth_permissions_staff(self):
        self.doTestGroupPermissions(self.authenticator, self.staffs[0])

    def test_transport_permissions_user(self):
        self.doTestUserPermissions(self.userService.deployed_service.transports.first(), self.users[0])

    def test_transport_permissions_admin(self):
        self.doTestUserPermissions(self.userService.deployed_service.transports.first(), self.admins[0])

    def test_transport_permissions_staff(self):
        self.doTestUserPermissions(self.userService.deployed_service.transports.first(), self.staffs[0])

    '''def test_user_transport_permissions(self):
        self.doTestUserPermissions(Transport.objects.all()[0])

    def test_group_transport_permissions(self):
        self.doTestGroupPermissions(Transport.objects.all()[0])

    def test_user_network_permissions(self):
        self.doTestUserPermissions(Network.objects.all()[0])

    def test_group_network_permissions(self):
        self.doTestGroupPermissions(Network.objects.all()[0])

    def test_user_provider_permissions(self):
        self.doTestUserPermissions(Provider.objects.all()[0])

    def test_group_provider_permissions(self):
        self.doTestGroupPermissions(Provider.objects.all()[0])

    def test_user_service_permissions(self):
        self.doTestUserPermissions(Service.objects.all()[0])

    def test_group_service_permissions(self):
        self.doTestGroupPermissions(Service.objects.all()[0])

    def test_user_pool_permissions(self):
        self.doTestUserPermissions(ServicePool.objects.all()[0])

    def test_group_pool_permissions(self):
        self.doTestGroupPermissions(ServicePool.objects.all()[0])
'''