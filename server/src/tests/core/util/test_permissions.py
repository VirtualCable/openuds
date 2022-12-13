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
from uds.core.util import objtype
from uds import models

from ...utils.test import UDSTestCase
from ...fixtures import (
    authenticators as authenticators_fixtures,
    services as services_fixtures,
    networks as network_fixtures,
)


class PermissionsTest(UDSTestCase):
    authenticator: models.Authenticator
    groups: typing.List[models.Group]
    users: typing.List[models.User]
    admins: typing.List[models.User]
    staffs: typing.List[models.User]
    userService: models.UserService
    servicePool: models.ServicePool
    service: models.Service
    provider: models.Provider
    network: models.Network

    def setUp(self) -> None:
        self.authenticator = authenticators_fixtures.createAuthenticator()
        self.groups = authenticators_fixtures.createGroups(self.authenticator)
        self.users = authenticators_fixtures.createUsers(
            self.authenticator, groups=self.groups
        )
        self.admins = authenticators_fixtures.createUsers(
            self.authenticator, is_admin=True, groups=self.groups
        )
        self.staffs = authenticators_fixtures.createUsers(
            self.authenticator, is_staff=True, groups=self.groups
        )
        self.userService = services_fixtures.createOneCacheTestingUserService(
            services_fixtures.createProvider(),
            self.users[0],
            list(self.users[0].groups.all()),
            'managed',
        )
        self.servicePool = self.userService.deployed_service
        self.service = self.servicePool.service
        self.provider = self.service.provider

        self.network = network_fixtures.createNetwork()

    def doTestUserPermissions(self, obj, user: models.User):
        permissions.addUserPermission(
            user, obj, permissions.PermissionType.PERMISSION_NONE
        )
        self.assertEqual(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, objtype.ObjectType.from_model(obj).type)
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_NONE)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            ),
            user.is_admin,
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_MANAGEMENT
            ),
            user.is_admin,
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            ),
            user.is_admin,
        )

        # Add a new permission, must overwrite the previous one
        permissions.addUserPermission(
            user, obj, permissions.PermissionType.PERMISSION_ALL
        )
        self.assertEqual(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, PermissionsTest.getObjectType(obj))
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_ALL)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_MANAGEMENT
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            )
        )

        # Again, with read
        permissions.addUserPermission(
            user, obj, permissions.PermissionType.PERMISSION_READ
        )
        self.assertEqual(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, PermissionsTest.getObjectType(obj))
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_READ)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            )
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_MANAGEMENT
            ),
            user.is_admin,
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            ),
            user.is_admin,
        )

        # Remove obj, permissions must have gone away
        obj.delete()
        self.assertEqual(models.Permissions.objects.count(), 0)

    def doTestGroupPermissions(self, obj, user: models.User):
        group = user.groups.all()[0]

        permissions.addGroupPermission(
            group, obj, permissions.PermissionType.PERMISSION_NONE
        )
        self.assertEqual(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, PermissionsTest.getObjectType(obj))
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_NONE)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        # Admins has all permissions ALWAYS
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            ),
            user.is_admin,
        )
        self.assertEqual(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            ),
            user.is_admin,
        )

        permissions.addGroupPermission(
            group, obj, permissions.PermissionType.PERMISSION_ALL
        )
        self.assertEqual(models.Permissions.objects.count(), 1)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, PermissionsTest.getObjectType(obj))
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_ALL)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            )
        )

        # Add user permission, DB must contain both an return ALL

        permissions.addUserPermission(
            user, obj, permissions.PermissionType.PERMISSION_READ
        )
        self.assertEqual(models.Permissions.objects.count(), 2)
        perm = models.Permissions.objects.all()[0]
        self.assertEqual(perm.object_type, PermissionsTest.getObjectType(obj))
        self.assertEqual(perm.object_id, obj.pk)
        self.assertEqual(perm.permission, permissions.PermissionType.PERMISSION_ALL)
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_NONE
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_READ
            )
        )
        self.assertTrue(
            permissions.checkPermissions(
                user, obj, permissions.PermissionType.PERMISSION_ALL
            )
        )

        # Remove obj, permissions must have gone away
        obj.delete()
        self.assertEqual(models.Permissions.objects.count(), 0)

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

    def test_user_servicepool_permissions_user(self):
        self.doTestUserPermissions(self.userService.deployed_service, self.users[0])

    def test_user_servicepool_permissions_admin(self):
        self.doTestUserPermissions(self.userService.deployed_service, self.admins[0])

    def test_user_servicepool_permissions_staff(self):
        self.doTestUserPermissions(self.userService.deployed_service, self.staffs[0])

    def test_group_servicepool_permissions_user(self):
        self.doTestGroupPermissions(self.userService.deployed_service, self.users[0])

    def test_group_servicepool_permissions_admin(self):
        self.doTestGroupPermissions(self.userService.deployed_service, self.admins[0])

    def test_group_servicepool_permissions_staff(self):
        self.doTestGroupPermissions(self.userService.deployed_service, self.staffs[0])

    def test_user_transport_permissions_user(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.transports.first(), self.users[0]
        )

    def test_user_transport_permissions_admin(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.transports.first(), self.admins[0]
        )

    def test_user_transport_permissions_staff(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.transports.first(), self.staffs[0]
        )

    def test_group_transport_permissions_user(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.transports.first(), self.users[0]
        )

    def test_group_transport_permissions_admin(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.transports.first(), self.admins[0]
        )

    def test_group_transport_permissions_staff(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.transports.first(), self.staffs[0]
        )

    def test_user_service_permissions_user(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service, self.users[0]
        )

    def test_user_service_permissions_admin(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service, self.admins[0]
        )

    def test_user_service_permissions_staff(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service, self.staffs[0]
        )

    def test_group_service_permissions_user(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service, self.users[0]
        )

    def test_group_service_permissions_admin(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service, self.admins[0]
        )

    def test_group_service_permissions_staff(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service, self.staffs[0]
        )

    def test_user_provider_permissions_user(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service.provider, self.users[0]
        )

    def test_user_provider_permissions_admin(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service.provider, self.admins[0]
        )

    def test_user_provider_permissions_staff(self):
        self.doTestUserPermissions(
            self.userService.deployed_service.service.provider, self.staffs[0]
        )

    def test_group_provider_permissions_user(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service.provider, self.users[0]
        )

    def test_group_provider_permissions_admin(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service.provider, self.admins[0]
        )

    def test_group_provider_permissions_staff(self):
        self.doTestGroupPermissions(
            self.userService.deployed_service.service.provider, self.staffs[0]
        )

    def test_user_network_permissions_user(self):
        self.doTestUserPermissions(self.network, self.users[0])

    def test_user_network_permissions_admin(self):
        self.doTestUserPermissions(self.network, self.admins[0])

    def test_user_network_permissions_staff(self):
        self.doTestUserPermissions(self.network, self.staffs[0])

    def test_group_network_permissions_user(self):
        self.doTestGroupPermissions(self.network, self.users[0])

    def test_group_network_permissions_admin(self):
        self.doTestGroupPermissions(self.network, self.admins[0])

    def test_group_network_permissions_staff(self):
        self.doTestGroupPermissions(self.network, self.staffs[0])

    @staticmethod
    def getObjectType(obj: typing.Type) -> int:
        return objtype.ObjectType.from_model(obj).type
