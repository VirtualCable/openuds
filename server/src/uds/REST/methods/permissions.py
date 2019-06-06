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

from uds.core.util import permissions

from uds.models import Provider, Service, Authenticator, OSManager, Transport, Network, ServicePool, Calendar, Account, MetaPool
from uds.models import User, Group

from uds.REST import Handler
from uds.REST import RequestError


logger = logging.getLogger(__name__)


# Enclosed methods under /permissions path
class Permissions(Handler):
    """
    Processes permissions requests
    """
    needs_admin = True

    @staticmethod
    def getClass(arg):
        cls = {
            'providers': Provider,
            'service': Service,
            'authenticators': Authenticator,
            'osmanagers': OSManager,
            'transports': Transport,
            'networks': Network,
            'servicespools': ServicePool,
            'calendars': Calendar,
            'metapools': MetaPool,
            'accounts': Account,
        }.get(arg, None)

        if cls is None:
            raise RequestError('Invalid request')

        return cls

    @staticmethod
    def permsToDict(perms):
        res = []
        for perm in perms:
            if perm.user is None:
                kind = 'group'
                entity = perm.group
            else:
                kind = 'user'
                entity = perm.user

            res.append({
                'id': perm.uuid,
                'type': kind,
                'auth': entity.manager.uuid,
                'auth_name': entity.manager.name,
                'entity_id': entity.uuid,
                'entity_name': entity.name,
                'perm': perm.permission,
                'perm_name': perm.permission_as_string
            })

        return sorted(res, key=lambda v: v['auth_name'] + v['entity_name'])

    def get(self):
        """
        Processes get requests
        """
        logger.debug('Permissions args for GET: %s', self._args)

        if len(self._args) != 2:
            raise RequestError('Invalid request')

        cls = Permissions.getClass(self._args[0])
        obj = cls.objects.get(uuid=self._args[1])

        perms = permissions.getPermissions(obj)

        return Permissions.permsToDict(perms)

    def put(self):
        """
        Processes put requests
        """
        logger.debug('Put args: %s', self._args)

        la = len(self._args)

        if la == 5 and self._args[3] == 'add':
            perm = {
                '0': permissions.PERMISSION_NONE,
                '1': permissions.PERMISSION_READ,
                '2': permissions.PERMISSION_MANAGEMENT,
                '3': permissions.PERMISSION_ALL
            }.get(self._params.get('perm', '0'), permissions.PERMISSION_NONE)

            cls = Permissions.getClass(self._args[0])

            obj = cls.objects.get(uuid=self._args[1])

            if self._args[2] == 'users':
                user = User.objects.get(uuid=self._args[4])
                permissions.addUserPermission(user, obj, perm)
            elif self._args[2] == 'groups':
                group = Group.objects.get(uuid=self._args[4])
                permissions.addGroupPermission(group, obj, perm)
            else:
                raise RequestError('Ivalid request')

            return Permissions.permsToDict(permissions.getPermissions(obj))
        elif la == 1 and self._args[0] == 'revoke':
            items = self._params.get('items', [])
            for permId in items:
                permissions.revokePermissionById(permId)
            return {}
        else:
            raise RequestError('Invalid request')
