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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

__updated__ = '2015-03-09'

from uds.models import Permissions
from uds.core.util import ot

import logging

logger = logging.getLogger(__name__)

PERMISSION_ALL = Permissions.PERMISSION_ALL
PERMISSION_READ = Permissions.PERMISSION_READ
PERMISSION_MANAGEMENT = Permissions.PERMISSION_MANAGEMENT
PERMISSION_NONE = Permissions.PERMISSION_NONE


def clean(obj):
    Permissions.cleanPermissions(ot.getObjectType(obj), obj.pk)


def getPermissions(obj):
    return list(Permissions.enumeratePermissions(object_type=ot.getObjectType(obj), object_id=obj.pk))


def getEffectivePermission(user, obj, root=False):
    if user.is_admin is True:
        return PERMISSION_ALL

    if user.staff_member is False:
        return PERMISSION_NONE

    if root is False:
        return Permissions.getPermissions(user=user, groups=user.groups.all(), object_type=ot.getObjectType(obj), object_id=obj.pk)
    else:
        return Permissions.getPermissions(user=user, groups=user.groups.all(), object_type=ot.getObjectType(obj))


def addUserPermission(user, obj, permission=PERMISSION_READ):
    # Some permissions added to some object types needs at least READ_PERMISSION on parent
    Permissions.addPermission(user=user, object_type=ot.getObjectType(obj), object_id=obj.pk, permission=permission)


def addGroupPermission(group, obj, permission=PERMISSION_READ):
    Permissions.addPermission(group=group, object_type=ot.getObjectType(obj), object_id=obj.pk, permission=permission)


def checkPermissions(user, obj, permission=PERMISSION_ALL, root=False):
    return getEffectivePermission(user, obj, root) >= permission


def getPermissionName(perm):
    return Permissions.permissionAsString(perm)


def revokePermissionById(permId):
    try:
        return Permissions.objects.get(uuid=permId).delete()
    except Exception:
        return None
