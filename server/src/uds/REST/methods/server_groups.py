# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
import logging
import re
import typing

from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from uds.core import types, consts
from uds.core.environment import Environment
from uds.core.ui import gui
from uds.core.util import permissions
from uds.core.util.model import processUuid
from uds.models import RegisteredServerGroup, RegisteredServer
from uds.REST import NotFound
from uds.REST.model import ModelHandler, DetailHandler

from .users_groups import Groups, Users

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from django.db import models

    from uds.core.module import Module

logger = logging.getLogger(__name__)


class TunnelServers(DetailHandler):
    custom_methods = ['servicesPools', 'users']

    def getItems(self, parent: 'RegisteredServerGroup', item: typing.Optional[str]):
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.groups.all().order_by('name')
            else:
                q = parent.groups.filter(uuid=processUuid(item))
            res = []
            i = None
            for i in q:
                val = {
                    'id': i.uuid,
                    'name': i.name,
                    'comments': i.comments,
                    'state': i.state,
                    'type': i.is_meta and 'meta' or 'group',
                    'meta_if_any': i.meta_if_any,
                }
                if i.is_meta:
                    val['groups'] = list(x.uuid for x in i.groups.all().order_by('name'))
                res.append(val)
            if multi:
                return res
            if not i:
                raise Exception('Item not found')
            # Add pools field if 1 item only
            result = res[0]
            result['pools'] = [v.uuid for v in getPoolsForGroups([i])]
            return result
        except Exception as e:
            logger.exception('REST groups')
            raise self.invalidItemException() from e

    def getTitle(self, parent: 'RegisteredServerGroup') -> str:
        try:
            return _('Groups of {0}').format(parent.name)
        except Exception:
            return _('Current groups')

    def getFields(self, parent: 'RegisteredServerGroup') -> typing.List[typing.Any]:
        return [
            {
                'name': {
                    'title': _('Group'),
                    'visible': True,
                    'type': 'icon_dict',
                    'icon_dict': {
                        'group': 'fa fa-group text-success',
                        'meta': 'fa fa-gears text-info',
                    },
                }
            },
            {'comments': {'title': _('Comments')}},
            {
                'state': {
                    'title': _('state'),
                    'type': 'dict',
                    'dict': State.dictionary(),
                }
            },
        ]

    def getTypes(self, parent: 'RegisteredServerGroup', forType: typing.Optional[str]):
        tDct = {
            'group': {'name': _('Group'), 'description': _('UDS Group')},
            'meta': {'name': _('Meta group'), 'description': _('UDS Meta Group')},
        }
        types = [
            {
                'name': v['name'],
                'type': k,
                'description': v['description'],
                'icon': '',
            }
            for k, v in tDct.items()
        ]

        if forType is None:
            return types

        try:
            return next(filter(lambda x: x['type'] == forType, types))
        except Exception:
            raise self.invalidRequestException() from None

    def saveItem(self, parent: 'RegisteredServerGroup', item: typing.Optional[str]) -> None:
        group = None  # Avoid warning on reference before assignment
        try:
            is_meta = self._params['type'] == 'meta'
            meta_if_any = self._params.get('meta_if_any', False)
            pools = self._params.get('pools', None)
            logger.debug('Saving group %s / %s', parent, item)
            logger.debug('Meta any %s', meta_if_any)
            logger.debug('Pools: %s', pools)
            valid_fields = ['name', 'comments', 'state']
            if self._params.get('name', '') == '':
                raise RequestError(_('Group name is required'))
            fields = self.readFieldsFromParams(valid_fields)
            is_pattern = fields.get('name', '').find('pat:') == 0
            auth = parent.getInstance()
            if not item:  # Create new
                if not is_meta and not is_pattern:
                    auth.createGroup(
                        fields
                    )  # this throws an exception if there is an error (for example, this auth can't create groups)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                toSave['comments'] = fields['comments'][:255]
                toSave['is_meta'] = is_meta
                toSave['meta_if_any'] = meta_if_any
                group = parent.groups.create(**toSave)
            else:
                if not is_meta and not is_pattern:
                    auth.modifyGroup(fields)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                del toSave['name']  # Name can't be changed
                toSave['comments'] = fields['comments'][:255]
                toSave['meta_if_any'] = meta_if_any

                group = parent.groups.get(uuid=processUuid(item))
                group.__dict__.update(toSave)

            if is_meta:
                # Do not allow to add meta groups to meta groups
                group.groups.set(
                    i for i in parent.groups.filter(uuid__in=self._params['groups']) if i.is_meta is False
                )

            if pools:
                # Update pools
                group.deployedServices.set(ServicePool.objects.filter(uuid__in=pools))

            group.save()
        except Group.DoesNotExist:
            raise self.invalidItemException() from None
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)')) from None
        except AuthenticatorException as e:
            raise RequestError(str(e)) from e
        except RequestError:  # pylint: disable=try-except-raise
            raise  # Re-raise
        except Exception as e:
            logger.exception('Saving group')
            raise self.invalidRequestException() from e

    def deleteItem(self, parent: 'RegisteredServerGroup', item: str) -> None:
        try:
            group = parent.groups.get(uuid=item)

            group.delete()
        except Exception:
            raise self.invalidItemException() from None


# Enclosed methods under /auth path
class Tunnels(ModelHandler):
    model = RegisteredServerGroup
    model_filter = {'kind': types.servers.Type.TUNNEL}

    detail = {'servers': TunnelServers}
    save_fields = ['name', 'comments', 'host:', 'port:0']

    table_title = _('Tunnels')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'comments': {'title': _('Comments')}},
        {'host': {'title': _('Host')}},
        {'servers_count': {'title': _('Users'), 'type': 'numeric', 'width': '1rem'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def getGui(self, type_: str) -> typing.List[typing.Any]:
        return self.addField(
            self.addDefaultFields([], ['name', 'comments', 'tags']),
            {
                'name': 'net_string',
                'value': '',
                'label': gettext('Network range'),
                'tooltip': gettext(
                    'Network range. Accepts most network definitions formats (range, subnet, host, etc...'
                ),
                'type': gui.InputField.Types.TEXT,
                'order': 100,  # At end
            },
        )

    def item_as_dict(self, item: 'RegisteredServer') -> typing.Dict[str, typing.Any]:
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'net_string': item.net_string,
            'transports_count': item.transports.count(),
            'authenticators_count': item.authenticators.count(),
            'permission': permissions.getEffectivePermission(self._user, item),
        }
