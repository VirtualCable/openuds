# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2020 Virtual Cable S.L.
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

from uds.core.util import permissions
from uds.core.util.rest.tools import match

from uds import models

from uds.REST import Handler
from uds.REST import RequestError

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

logger = logging.getLogger(__name__)


# Enclosed methods under /permissions path
class Permissions(Handler):
    """
    Processes permissions requests
    """

    needs_admin = True

    @staticmethod
    def getClass(arg: str) -> typing.Type['Model']:
        cls = {
            'providers': models.Provider,
            'service': models.Service,
            'authenticators': models.Authenticator,
            'osmanagers': models.OSManager,
            'transports': models.Transport,
            'networks': models.Network,
            'servicespools': models.ServicePool,
            'calendars': models.Calendar,
            'metapools': models.MetaPool,
            'accounts': models.Account,
        }.get(arg, None)

        if cls is None:
            raise RequestError('Invalid request')

        return cls

    @staticmethod
    def permsToDict(
        perms: typing.Iterable[models.Permissions],
    ) -> typing.List[typing.Dict[str, str]]:
        res = []
        for perm in perms:
            if perm.user is None:
                kind = 'group'
                entity = perm.group
            else:
                kind = 'user'
                entity = perm.user

            # If entity is None, it means that the permission is not valid anymore (user or group deleted on db manually?)
            if not entity:
                continue

            res.append(
                {
                    'id': perm.uuid,
                    'type': kind,
                    'auth': entity.manager.uuid,  # type: ignore
                    'auth_name': entity.manager.name,  # type: ignore
                    'entity_id': entity.uuid,  # type: ignore
                    'entity_name': entity.name,  # type: ignore
                    'perm': perm.permission,
                    'perm_name': perm.permission_as_string,
                }
            )

        return sorted(res, key=lambda v: v['auth_name'] + v['entity_name'])

    def get(self) -> typing.Any:
        """
        Processes get requests
        """
        logger.debug('Permissions args for GET: %s', self._args)

        if len(self._args) != 2:
            raise RequestError('Invalid request')

        itemClass = Permissions.getClass(self._args[0])
        obj: 'Model' = itemClass.objects.get(uuid=self._args[1])

        return Permissions.permsToDict(permissions.getPermissions(obj))

    def put(self) -> typing.List[typing.Dict]:
        """
        Processes put requests
        """
        logger.debug('Put args: %s', self._args)

        la = len(self._args)

        perm = permissions.PermissionType.from_str(self._params.get('perm', '0'))

        def add_user_permission(cls_param: str, obj_param: str, user_param: str) -> typing.List[typing.Dict]:
            cls = Permissions.getClass(cls_param)
            obj = cls.objects.get(uuid=obj_param)
            user = models.User.objects.get(uuid=user_param)
            permissions.addUserPermission(user, obj, perm)
            return Permissions.permsToDict(permissions.getPermissions(obj))

        def add_group_permission(cls_param: str, obj_param: str, group_param: str) -> typing.List[typing.Dict]:
            cls = Permissions.getClass(cls_param)
            obj = cls.objects.get(uuid=obj_param)
            group = models.Group.objects.get(uuid=group_param)
            permissions.addGroupPermission(group, obj, perm)
            return Permissions.permsToDict(permissions.getPermissions(obj))

        def revoke() -> typing.List[typing.Dict]:
            for permId in self._params.get('items', []):
                permissions.revokePermissionById(permId)
            return []

        def no_match() -> None:
            raise RequestError('Invalid request')

        # match is a helper function that will match the args with the given patterns
        return match(self._args,
            no_match,
            (('<cls>', '<obl>', 'users', 'add', '<user>'), add_user_permission),
            (('<cls>', '<obl>', 'groups', 'add', '<group>'), add_group_permission),
            (('revoke', ), revoke)
        )

        if la == 5 and self._args[3] == 'add':

            cls = Permissions.getClass(self._args[0])

            obj = cls.objects.get(uuid=self._args[1])

            if self._args[2] == 'users':
                user = models.User.objects.get(uuid=self._args[4])
                permissions.addUserPermission(user, obj, perm)
            elif self._args[2] == 'groups':
                group = models.Group.objects.get(uuid=self._args[4])
                permissions.addGroupPermission(group, obj, perm)
            else:
                raise RequestError('Ivalid request')
            return Permissions.permsToDict(permissions.getPermissions(obj))

        if la == 1 and self._args[0] == 'revoke':
            for permId in self._params.get('items', []):
                permissions.revokePermissionById(permId)
            return []

        raise RequestError('Invalid request')
