# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

# from django.utils.translation import gettext as _

from uds import models
from uds.core.types.permissions import PermissionType

from uds.core.util import objtype


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


def clean(obj: 'Model') -> None:
    models.Permissions.clean_permissions(objtype.ObjectType.from_model(obj), obj.pk)


def getPermissions(obj: 'Model') -> list[models.Permissions]:
    return list(
        models.Permissions.enumerate_permissions(
            object_type=objtype.ObjectType.from_model(obj), object_id=obj.pk
        )
    )


def effective_permissions(
    user: 'models.User', obj: 'Model', for_type: bool = False
) -> PermissionType:
    try:
        if user.is_admin:
            return PermissionType.ALL

        # Just check permissions for staff members
        # root means for "object type" not for an object
        if for_type is False:
            return models.Permissions.get_permissions(
                object_type=objtype.ObjectType.from_model(obj),
                user=user,
                object_id=obj.pk,
                groups=user.groups.all(),
            )

        return models.Permissions.get_permissions(
            object_type=objtype.ObjectType.from_model(obj),
            user=user,
            groups=user.groups.all(),
        )
    except Exception:
        return PermissionType.NONE


def add_user_permission(
    user: 'models.User',
    obj: 'Model',
    permission: PermissionType = PermissionType.READ,
) -> None:
    # Some permissions added to some object types needs at least READ_PERMISSION on parent
    models.Permissions.add_permission(
        user=user,
        object_type=objtype.ObjectType.from_model(obj),
        object_id=obj.pk,
        permission=permission,
    )


def add_group_permission(
    group: 'models.Group',
    obj: 'Model',
    permission: PermissionType = PermissionType.READ,
) -> None:
    models.Permissions.add_permission(
        group=group,
        object_type=objtype.ObjectType.from_model(obj),
        object_id=obj.pk,
        permission=permission,
    )


def has_access(
    user: 'models.User',
    obj: 'Model',
    permission: PermissionType = PermissionType.ALL,
    for_type: bool = False,
) -> bool:
    return effective_permissions(user, obj, for_type).contains(permission)


def revoke_permission_by_id(permUUID: str) -> None:
    """Revokes a permision by its uuid

    Arguments:
        permUUID {str} -- uuid of permission

    """
    try:
        models.Permissions.objects.get(uuid=permUUID).delete()
    except Exception:
        # no pemission found, log it
        logger.warning('Permission %s not found', permUUID)
