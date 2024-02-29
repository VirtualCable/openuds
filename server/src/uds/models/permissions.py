# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import collections.abc
import logging

from django.utils.translation import gettext as _
from django.db import models
from django.db.models import Q

from uds.core.types.permissions import PermissionType

from .uuid_model import UUIDModel
from .user import User
from .group import Group
from ..core.util.model import sql_datetime

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from uds.models import User, Group
    from uds.core.util import objtype


class Permissions(UUIDModel):
    """
    An OS Manager represents a manager for responding requests for agents inside services.
    """

    # Allowed permissions

    created = models.DateTimeField(db_index=True)
    ends = models.DateTimeField(
        db_index=True, null=True, blank=True, default=None
    )  # Future "permisions ends at this moment", not assigned right now

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='permissions',
        null=True,
        blank=True,
        default=None,
    )
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='permissions',
        null=True,
        blank=True,
        default=None,
    )

    object_type = models.SmallIntegerField(default=-1, db_index=True)
    object_id = models.IntegerField(default=None, db_index=True, null=True, blank=True)

    permission = models.SmallIntegerField(default=PermissionType.NONE, db_index=True)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[Permissions]'

    @staticmethod
    def add_permission(
        *,
        user: typing.Optional['User'] = None,
        group: typing.Optional['Group'] = None,
        object_type: 'objtype.ObjectType',
        object_id: typing.Optional[int] = None,
        permission: PermissionType = PermissionType.NONE,
    ) -> 'Permissions':
        """
        Adds a permission to an object and an user or group
        """
        if user and group:
            raise Exception('Use only user or group, but not both')

        if user is None and group is None:
            raise Exception('Must at least indicate user or group')

        if user is not None:
            q = Q(user=user)
        else:
            q = Q(group=group)

        try:
            existing: Permissions = Permissions.objects.filter(
                q, object_type=object_type.type, object_id=object_id
            )[0]
            existing.permission = permission
            existing.save()
            return existing
        except Exception:  # Does not exists
            return Permissions.objects.create(
                created=sql_datetime(),
                ends=None,
                user=user,
                group=group,
                object_type=object_type.type,
                object_id=object_id,
                permission=permission,
            )

    @staticmethod
    def get_permissions(
        object_type: 'objtype.ObjectType',
        object_id: typing.Optional[int] = None,
        user: typing.Optional['User'] = None,
        groups: typing.Optional[collections.abc.Iterable['Group']] = None,
    ) -> PermissionType:
        """
        Retrieves the permission for a given object
        It's mandatory to include at least object_type param

        @param object_type: Required
        @param object_id: Optional
        @param user: Optional, User (db object)
        @param groups: Optional List of db groups
        """
        if not user and not groups:
            q = Q()
        else:
            q = Q(user=user)
            if groups:
                q |= Q(group__in=groups)

        try:
            perm: Permissions = Permissions.objects.filter(
                Q(object_type=object_type.type),
                Q(object_id=None) | Q(object_id=object_id),
                q,
            ).order_by('-permission')[0]
            logger.debug('Got permission %s', perm)
            return PermissionType(perm.permission)
        except Exception:  # DoesNotExists
            return PermissionType.NONE

    @staticmethod
    def enumerate_permissions(
        object_type: 'objtype.ObjectType', object_id: int
    ) -> 'models.QuerySet[Permissions]':
        """
        Get users permissions over object
        """
        return Permissions.objects.filter(object_type=object_type.type, object_id=object_id)

    @staticmethod
    def clean_permissions(
        object_type: 'objtype.ObjectType',
        object_id: int,
        user: typing.Optional['User'] = None,
        group: typing.Optional['Group'] = None,
    ) -> None:
        if user and group:  # Using both is same as using none
            user = None
            group = None
        if not user and not group:
            q = Q()
        elif user:
            q = Q(user=user)
        else:
            q = Q(group=group)

        Permissions.objects.filter(Q(object_type=object_type.type), Q(object_id=object_id), q).delete()

    @property
    def as_str(self) -> str:
        return PermissionType(self.permission).as_str()

    def __str__(self) -> str:
        return (
            f'Permission {self.uuid}, user {self.user} group {self.group} '
            f'object_type {self.object_type} object_id {self.object_id} '
            f'permission {PermissionType(self.permission).as_str()}'
        )
