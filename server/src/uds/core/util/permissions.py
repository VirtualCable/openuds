# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import logging
import typing
from uds.REST.methods.permissions import Permissions

from uds import models
from uds.core.util import ot

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)

PERMISSION_ALL = models.Permissions.PERMISSION_ALL
PERMISSION_READ = models.Permissions.PERMISSION_READ
PERMISSION_MANAGEMENT = models.Permissions.PERMISSION_MANAGEMENT
PERMISSION_NONE = models.Permissions.PERMISSION_NONE


def clean(obj: 'Model') -> None:
    models.Permissions.cleanPermissions(ot.getObjectType(obj), obj.pk)


def getPermissions(obj: 'Model') -> typing.List[models.Permissions]:
    return list(models.Permissions.enumeratePermissions(object_type=ot.getObjectType(obj), object_id=obj.pk))


def getEffectivePermission(user: 'models.User', obj: 'Model', root: bool = False) -> int:
    try:
        if user.is_admin is True:
            return PERMISSION_ALL

        if user.staff_member is False:
            return PERMISSION_NONE

        if root is False:
            return models.Permissions.getPermissions(user=user, groups=user.groups.all(), object_type=ot.getObjectType(obj), object_id=obj.pk)

        return models.Permissions.getPermissions(user=user, groups=user.groups.all(), object_type=ot.getObjectType(obj))
    except Exception:
        return PERMISSION_NONE


def addUserPermission(user: 'models.User', obj: 'Model', permission: int = PERMISSION_READ):
    # Some permissions added to some object types needs at least READ_PERMISSION on parent
    models.Permissions.addPermission(user=user, object_type=ot.getObjectType(obj), object_id=obj.pk, permission=permission)


def addGroupPermission(group: 'models.Group', obj: 'Model', permission: int = PERMISSION_READ):
    models.Permissions.addPermission(group=group, object_type=ot.getObjectType(obj), object_id=obj.pk, permission=permission)


def checkPermissions(user: 'models.User', obj: 'Model', permission: int = PERMISSION_ALL, root: bool = False):
    return getEffectivePermission(user, obj, root) >= permission


def getPermissionName(perm: int) -> str:
    return models.Permissions.permissionAsString(perm)


def revokePermissionById(permUUID: str) -> None:
    """Revokes a permision by its uuid

    Arguments:
        permUUID {str} -- uuid of permission

    """
    try:
        models.Permissions.objects.get(uuid=permUUID).delete()
    except Exception:
        pass
