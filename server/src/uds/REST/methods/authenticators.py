# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2024 Virtual Cable S.L.U.
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import logging
import re
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import auths, consts, exceptions, types
from uds.core.environment import Environment
from uds.core.ui import gui
from uds.core.util import ensure, permissions
from uds.core.util.model import process_uuid
from uds.models import MFA, Authenticator, Network
from uds.REST.model import ModelHandler

from .users_groups import Groups, Users

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db.models import Model

    from uds.core.module import Module

logger = logging.getLogger(__name__)


# Enclosed methods under /auth path
class Authenticators(ModelHandler):
    model = Authenticator
    # Custom get method "search" that requires authenticator id
    custom_methods = [('search', True)]
    detail = {'users': Users, 'groups': Groups}
    save_fields = ['name', 'comments', 'tags', 'priority', 'small_name', 'mfa_id:_']

    table_title = typing.cast(str, _('Authenticators'))
    table_fields = [
        {'numeric_id': {'title': _('Id'), 'visible': True}},
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'type_name': {'title': _('Type')}},
        {'comments': {'title': _('Comments')}},
        {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '5rem'}},
        {'small_name': {'title': _('Label')}},
        {'users_count': {'title': _('Users'), 'type': 'numeric', 'width': '1rem'}},
        {
            'mfa_name': {
                'title': _('MFA'),
            }
        },
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self) -> collections.abc.Iterable[type[auths.Authenticator]]:
        return auths.factory().providers().values()

    def type_info(self, type_: type['Module']) -> dict[str, typing.Any]:
        if issubclass(type_, auths.Authenticator):
            return {
                'search_users_supported': type_.search_users != auths.Authenticator.search_users,
                'search_groups_supported': type_.search_groups != auths.Authenticator.search_groups,
                'needs_password': type_.needs_password,
                'label_username': _(type_.label_username),
                'label_groupname': _(type_.label_groupname),
                'label_password': _(type_.label_password),
                'create_users_supported': type_.create_user != auths.Authenticator.create_user,
                'is_external': type_.external_source,
                'mfa_supported': type_.provides_mfa(),
            }
        # Not of my type
        return {}

    def get_gui(self, type_: str) -> list[typing.Any]:
        try:
            authType = auths.factory().lookup(type_)
            if authType:
                # Create a new instance of the authenticator to access to its GUI
                with Environment.temporary_environment() as env:
                    authInstance = authType(env, None)
                    field = self.add_default_fields(
                        authInstance.gui_description(),
                        ['name', 'comments', 'tags', 'priority', 'small_name', 'networks'],
                    )
                    self.add_field(
                        field,
                        {
                            'name': 'state',
                            'value': consts.auth.VISIBLE,
                            'choices': [
                                {'id': consts.auth.VISIBLE, 'text': _('Visible')},
                                {'id': consts.auth.HIDDEN, 'text': _('Hidden')},
                                {'id': consts.auth.DISABLED, 'text': _('Disabled')},
                            ],
                            'label': gettext('Access'),
                            'tooltip': gettext(
                                'Access type for this transport. Disabled means not only hidden, but also not usable as login method.'
                            ),
                            'type': types.ui.FieldType.CHOICE,
                            'order': 107,
                            'tab': gettext('Display'),
                        },
                    )
                    # If supports mfa, add MFA provider selector field
                    if authType.provides_mfa():
                        self.add_field(
                            field,
                            {
                                'name': 'mfa_id',
                                'choices': [gui.choice_item('', typing.cast(str, _('None')))]
                                + gui.sorted_choices(
                                    [gui.choice_item(v.uuid or '', v.name) for v in MFA.objects.all()]
                                ),
                                'label': gettext('MFA Provider'),
                                'tooltip': gettext('MFA provider to use for this authenticator'),
                                'type': types.ui.FieldType.CHOICE,
                                'order': 108,
                                'tab': types.ui.Tab.MFA,
                            },
                        )
                    return field
            raise Exception()  # Not found
        except Exception as e:
            logger.info('Type not found: %s', e)
            raise exceptions.rest.NotFound('type not found') from e

    def item_as_dict(self, item: 'Model') -> dict[str, typing.Any]:
        summary = 'summarize' in self._params

        item = ensure.is_instance(item, Authenticator)
        v = {
            'numeric_id': item.id,
            'id': item.uuid,
            'name': item.name,
            'priority': item.priority,
        }
        if not summary:
            type_ = item.get_type()
            v.update(
                {
                    'tags': [tag.tag for tag in item.tags.all()],
                    'comments': item.comments,
                    'net_filtering': item.net_filtering,
                    'networks': [{'id': n.uuid} for n in item.networks.all()],
                    'state': item.state,
                    'mfa_id': item.mfa.uuid if item.mfa else '',
                    'small_name': item.small_name,
                    'users_count': item.users.count(),
                    'type': type_.get_type(),
                    'type_name': type_.name(),
                    'type_info': self.type_info(type_),
                    'permission': permissions.effective_permissions(self._user, item),
                }
            )
        return v

    def post_save(self, item: 'Model') -> None:
        item = ensure.is_instance(item, Authenticator)
        try:
            networks = self._params['networks']
        except Exception:  # No networks passed in, this is ok
            logger.debug('No networks')
            return
        if networks is None:  # None is not provided, empty list is ok and means no networks
            return
        logger.debug('Networks: %s', networks)
        item.networks.set(Network.objects.filter(uuid__in=networks))

    # Custom "search" method
    def search(self, item: 'Model') -> list[types.rest.ItemDictType]:
        item = ensure.is_instance(item, Authenticator)
        self.ensure_has_access(item, types.permissions.PermissionType.READ)
        try:
            type_ = self._params['type']
            if type_ not in ('user', 'group'):
                raise self.invalid_request_response()

            term = self._params['term']

            limit = int(self._params.get('limit', '50'))

            auth = item.get_instance()

            canDoSearch = (
                type_ == 'user'
                and (auth.search_users != auths.Authenticator.search_users)
                or (auth.search_groups != auths.Authenticator.search_groups)
            )
            if canDoSearch is False:
                raise self.not_supported_response()

            if type_ == 'user':
                return list(auth.search_users(term))[:limit]
            return list(auth.search_groups(term))[:limit]
        except Exception as e:
            logger.exception('Too many results: %s', e)
            return [{'id': _('Too many results...'), 'name': _('Refine your query')}]
            # self.invalidResponseException('{}'.format(e))

    def test(self, type_: str) -> typing.Any:
        authType = auths.factory().lookup(type_)
        if not authType:
            raise self.invalid_request_response(f'Invalid type: {type_}')

        dct = self._params.copy()
        dct['_request'] = self._request
        with Environment.temporary_environment() as env:
            res = authType.test(env, dct)
            if res[0]:
                return self.success()
            return res[1]

    def pre_save(
        self, fields: dict[str, typing.Any]
    ) -> None:  # pylint: disable=too-many-branches,too-many-statements
        logger.debug(self._params)
        if fields.get('mfa_id'):
            try:
                mfa = MFA.objects.get(uuid=process_uuid(fields['mfa_id']))
                fields['mfa_id'] = mfa.id
            except MFA.DoesNotExist:
                pass  # will set field to null
        else:
            fields['mfa_id'] = None

        # If label has spaces, replace them with underscores
        fields['small_name'] = fields['small_name'].strip().replace(' ', '_')
        # And ensure small_name chars are valid [a-zA-Z0-9:-]+
        if fields['small_name'] and not re.match(r'^[a-zA-Z0-9:.-]+$', fields['small_name']):
            raise self.invalid_request_response(
                typing.cast(str, _('Label must contain only letters, numbers, or symbols: - : .'))
            )

    def delete_item(self, item: 'Model') -> None:
        # For every user, remove assigned services (mark them for removal)
        item = ensure.is_instance(item, Authenticator)

        for user in item.users.all():
            for userService in user.userServices.all():
                userService.user = None
                userService.remove_or_cancel()

        item.delete()
