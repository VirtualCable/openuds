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
#      and/or other materials provided with the distribution
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import ugettext_lazy as _
from uds.models import Authenticator
from uds.core import auths

from uds.REST import NotFound
from uds.REST.model import ModelHandler
from uds.core.util import permissions

from .users_groups import Users, Groups

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import Module

logger = logging.getLogger(__name__)


# Enclosed methods under /auth path
class Authenticators(ModelHandler):
    model = Authenticator
    # Custom get method "search" that requires authenticator id
    custom_methods = [('search', True)]
    detail = {'users': Users, 'groups': Groups}
    save_fields = ['name', 'comments', 'tags', 'priority', 'small_name']

    table_title = _('Authenticators')
    table_fields = [
        {'numeric_id': {'title': _('Id'), 'visible': True}},
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'comments': {'title': _('Comments')}},
        {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '5em'}},
        {'small_name': {'title': _('Label')}},
        {'users_count': {'title': _('Users'), 'type': 'numeric', 'width': '5em'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self) -> typing.Iterable[typing.Type[auths.Authenticator]]:  # override this
        return auths.factory().providers().values()

    def typeInfo(self, type_: typing.Type['Module']) -> typing.Dict[str, typing.Any]:
        if issubclass(type_, auths.Authenticator):
            return {
                'canSearchUsers': type_.searchUsers != auths.Authenticator.searchUsers,
                'canSearchGroups': type_.searchGroups != auths.Authenticator.searchGroups,
                'needsPassword': type_.needsPassword,
                'userNameLabel': _(type_.userNameLabel),
                'groupNameLabel': _(type_.groupNameLabel),
                'passwordLabel': _(type_.passwordLabel),
                'canCreateUsers': type_.createUser != auths.Authenticator.createUser,
                'isExternal': type_.isExternalSource,
            }
        # Not of my type
        return {}

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        try:
            gui = auths.factory().lookup(type_)
            if gui:
                return self.addDefaultFields(gui.guiDescription(), ['name', 'comments', 'tags', 'priority', 'small_name'])
            raise Exception()  # Not found
        except Exception:
            raise NotFound('type not found')

    def item_as_dict(self, item: Authenticator) -> typing.Dict[str, typing.Any]:
        type_ = item.getType()
        return {
            'numeric_id': item.id,
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'priority': item.priority,
            'small_name': item.small_name,
            'users_count': item.users.count(),
            'type': type_.type(),
            'type_name': type_.name(),
            'type_info': self.typeInfo(type_),
            'permission': permissions.getEffectivePermission(self._user, item)
        }

    # Custom "search" method
    def search(self, item: Authenticator) -> typing.List[typing.Dict]:
        self.ensureAccess(item, permissions.PERMISSION_READ)
        try:
            type_ = self._params['type']
            if type_ not in ('user', 'group'):
                self.invalidRequestException()

            term = self._params['term']

            limit = int(self._params.get('limit', '50'))

            auth = item.getInstance()

            canDoSearch = type_ == 'user' and (auth.searchUsers != auths.Authenticator.searchUsers) or (auth.searchGroups != auths.Authenticator.searchGroups)
            if canDoSearch is False:
                self.notSupported()

            if type_ == 'user':
                return list(auth.searchUsers(term))[:limit]
            else:
                return list(auth.searchGroups(term))[:limit]
        except Exception as e:
            logger.exception('Too many results: %s', e)
            return [{'id': _('Too many results...'), 'name': _('Refine your query')}]
            # self.invalidResponseException('{}'.format(e))

    def test(self, type_: str):
        from uds.core.environment import Environment

        authType = auths.factory().lookup(type_)
        if not authType:
            self.invalidRequestException('Invalid type: {}'.format(type_))
            return False

        self.ensureAccess(authType, permissions.PERMISSION_MANAGEMENT, root=True)

        dct = self._params.copy()
        dct['_request'] = self._request
        res = authType.test(Environment.getTempEnv(), dct)
        if res[0]:
            return self.success()
        return res[1]

    def deleteItem(self, item: Authenticator):
        # For every user, remove assigned services (mark them for removal)

        for user in item.users.all():
            for userService in user.userServices.all():
                userService.user = None
                userService.removeOrCancel()

        item.delete()
