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
import datetime
import logging
import typing
import collections.abc

from django.utils.translation import gettext as _
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from uds.core.types.states import State

from uds.core.auths.user import User as AUser
from uds.core.util import log, ensure
from uds.core.util.rest.tools import as_typed_dict
from uds.core.util.model import process_uuid, sql_stamp_seconds
from uds.models import Authenticator, User, Group, ServicePool
from uds.core.managers.crypto import CryptoManager
from uds.core import consts, exceptions, types

from uds.REST.model import DetailHandler

from .user_services import AssignedUserService, UserServiceItem

if typing.TYPE_CHECKING:
    from django.db.models import Model
    from uds.models import UserService


logger = logging.getLogger(__name__)

# Details of /auth


def get_groups_from_metagroup(groups: collections.abc.Iterable[Group]) -> collections.abc.Iterable[Group]:
    for g in groups:
        if g.is_meta:
            for x in g.groups.all():
                yield x
        else:
            yield g


def get_service_pools_for_groups(
    groups: collections.abc.Iterable[Group],
) -> collections.abc.Iterable[ServicePool]:
    for servicepool in ServicePool.get_pools_for_groups(groups):
        yield servicepool


class UserItem(types.rest.ItemDictType):
    id: str
    name: str
    real_name: str
    comments: str
    state: str
    staff_member: bool
    is_admin: bool
    last_access: datetime.datetime
    parent: typing.NotRequired[str]
    mfa_data: str
    role: str
    groups: typing.NotRequired[list[str]]


class Users(DetailHandler[UserItem]):
    custom_methods = [
        'services_pools',
        'user_services',
        'clean_related',
        'add_to_group',
        'enable_client_logging',
    ]

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, Authenticator)

        def as_user_item(model: 'User') -> UserItem:
            base = as_typed_dict(
                model,
                UserItem,
            )
            # Convert uuid to id, that is what the frontend expects (instaad of the numeric id)
            base['id'] = model.uuid
            base['role'] = (
                model.staff_member and (model.is_admin and _('Admin') or _('Staff member')) or _('User')
            )
            return base

        # Extract authenticator
        try:
            if item is None:
                return [as_user_item(i) for i in parent.users.all()]

            u = parent.users.get(uuid__iexact=process_uuid(item))
            res = as_user_item(u)
            usr = AUser(u)
            res['groups'] = [g.db_obj().uuid for g in usr.groups()]
            logger.debug('Item: %s', res)
            return res
        except Exception as e:
            # User not found
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        try:
            return _('Users of {0}').format(
                Authenticator.objects.get(uuid=process_uuid(self._kwargs['parent_id'])).name
            )
        except Exception:
            return _('Current users')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {
                'name': {
                    'title': _('Username'),
                    'visible': True,
                    'type': 'icon',
                    'icon': 'fa fa-user text-success',
                }
            },
            {'role': {'title': _('Role')}},
            {'real_name': {'title': _('Name')}},
            {'comments': {'title': _('Comments')}},
            {
                'state': {
                    'title': _('state'),
                    'type': 'dict',
                    'dict': {State.ACTIVE: _('Enabled'), State.INACTIVE: _('Disabled')},
                }
            },
            {'last_access': {'title': _('Last access'), 'type': 'datetime'}},
        ]

    def get_row_style(self, parent: 'Model') -> types.ui.RowStyleInfo:
        return types.ui.RowStyleInfo(prefix='row-state-', field='state')

    def get_logs(self, parent: 'Model', item: str) -> list[typing.Any]:
        parent = ensure.is_instance(parent, Authenticator)
        user = None
        try:
            user = parent.users.get(uuid=process_uuid(item))
        except Exception:
            raise self.invalid_item_response() from None

        return log.get_logs(user)

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, Authenticator)
        logger.debug('Saving user %s / %s', parent, item)
        valid_fields = [
            'name',
            'real_name',
            'comments',
            'state',
            'staff_member',
            'is_admin',
        ]
        if self._params.get('name', '').strip() == '':
            raise exceptions.rest.RequestError(_('Username cannot be empty'))

        if 'password' in self._params:
            valid_fields.append('password')
            self._params['password'] = CryptoManager().hash(self._params['password'])

        if 'mfa_data' in self._params:
            valid_fields.append('mfa_data')
            self._params['mfa_data'] = self._params['mfa_data'].strip()

        fields = self.fields_from_params(valid_fields)
        if not self._user.is_admin:
            del fields['staff_member']
            del fields['is_admin']

        user = None
        try:
            with transaction.atomic():
                auth = parent.get_instance()
                if item is None:  # Create new
                    auth.create_user(
                        fields
                    )  # this throws an exception if there is an error (for example, this auth can't create users)
                    user = parent.users.create(**fields)
                else:
                    auth.modify_user(fields)  # Notifies authenticator
                    user = parent.users.get(uuid=process_uuid(item))
                    user.__dict__.update(fields)
                    user.save()

                logger.debug('User parent: %s', user.parent)
                # If internal auth, and not a child user, save groups
                if not auth.external_source and not user.parent:
                    groups = self.fields_from_params(['groups'])['groups']
                    # Save but skip meta groups, they are not real groups, but just a way to group users based on rules
                    user.groups.set(g for g in parent.groups.filter(uuid__in=groups) if g.is_meta is False)

                return {'id': user.uuid}
        except User.DoesNotExist:
            raise self.invalid_item_response() from None
        except IntegrityError:  # Duplicate key probably
            raise exceptions.rest.RequestError(_('User already exists (duplicate key error)')) from None
        except ValidationError as e:
            raise exceptions.rest.RequestError(str(e.message)) from e
        except exceptions.auth.AuthenticatorException as e:
            raise exceptions.rest.RequestError(str(e)) from e
        except exceptions.rest.RequestError:
            raise  # Re-raise
        except Exception as e:
            logger.exception('Saving user')
            raise self.invalid_request_response() from e

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Authenticator)
        try:
            user = parent.users.get(uuid=process_uuid(item))
            if not self._user.is_admin and (user.is_admin or user.staff_member):
                logger.warning(
                    'Removal of user %s denied due to insufficients rights',
                    user.pretty_name,
                )
                raise self.invalid_item_response(
                    f'Removal of user {user.pretty_name} denied due to insufficients rights'
                )

            assigned_userservice: 'UserService'
            for assigned_userservice in user.userServices.all():
                try:
                    assigned_userservice.user = None
                    assigned_userservice.save(update_fields=['user'])
                    assigned_userservice.remove_or_cancel()
                except Exception:
                    logger.exception('Removing user service')
                    try:
                        assigned_userservice.save()
                    except Exception:
                        logger.exception('Saving user on removing error')

            user.delete()
        except Exception as e:
            logger.error('Error on user removal of %s.%s:  %s', parent.name, item, e)
            raise self.invalid_item_response() from e

    def services_pools(self, parent: 'Model', item: str) -> list[dict[str, typing.Any]]:
        """
        API:
            Returns the service pools assigned to a user
        """
        parent = ensure.is_instance(parent, Authenticator)
        uuid = process_uuid(item)
        user = parent.users.get(uuid=process_uuid(uuid))
        res: list[dict[str, typing.Any]] = []
        groups = list(user.get_groups())
        for i in get_service_pools_for_groups(groups):
            res.append(
                {
                    'id': i.uuid,
                    'name': i.name,
                    'thumb': i.image.thumb64 if i.image is not None else consts.images.DEFAULT_THUMB_BASE64,
                    'user_services_count': i.userServices.exclude(
                        state__in=(State.REMOVED, State.ERROR)
                    ).count(),
                    'state': _('With errors') if i.is_restrained() else _('Ok'),
                }
            )

        return res

    def user_services(self, parent: 'Authenticator', item: str) -> list[UserServiceItem]:
        parent = ensure.is_instance(parent, Authenticator)
        uuid = process_uuid(item)
        user = parent.users.get(uuid=process_uuid(uuid))

        def item_as_dict(assigned_user_service: 'UserService') -> UserServiceItem:
            base = AssignedUserService.item_as_dict(assigned_user_service)
            base['pool'] = assigned_user_service.deployed_service.name
            base['pool_id'] = assigned_user_service.deployed_service.uuid
            return base

        return [
            item_as_dict(i)
            for i in user.userServices.all().prefetch_related('deployed_service').filter(state=State.USABLE)
        ]

    def clean_related(self, parent: 'Authenticator', item: str) -> dict[str, str]:
        uuid = process_uuid(item)
        user = parent.users.get(uuid=process_uuid(uuid))
        user.clean_related_data()
        return {'status': 'ok'}

    def add_to_group(self, parent: 'Authenticator', item: str) -> dict[str, str]:
        uuid = process_uuid(item)
        user = parent.users.get(uuid=process_uuid(uuid))
        group = parent.groups.get(uuid=process_uuid(self._params['group']))
        user.log(
            f'Added to group {group.name} by {self._user.pretty_name}',
            types.log.LogLevel.INFO,
            types.log.LogSource.REST,
        )
        user.groups.add(group)
        return {'status': 'ok'}

    def enable_client_logging(self, parent: 'Model', item: str) -> dict[str, str]:
        parent = ensure.is_instance(parent, Authenticator)
        user = parent.users.get(uuid=process_uuid(item))
        user.log(
            f'Client logging enabled by {self._user.pretty_name}',
            types.log.LogLevel.INFO,
            types.log.LogSource.REST,
        )
        with user.properties as props:
            props['client_logging'] = sql_stamp_seconds()

        return {'status': 'ok'}


class GroupItem(typing.TypedDict):
    id: str
    name: str
    comments: str
    state: str
    type: str
    meta_if_any: bool
    skip_mfa: str
    groups: typing.NotRequired[list[str]]  # Only for meta groups
    pools: typing.NotRequired[list[str]]  # Only for single group items


class Groups(DetailHandler[GroupItem]):
    custom_methods = ['services_pools', 'users']

    def get_items(self, parent: 'Model', item: typing.Optional[str]) -> types.rest.GetItemsResult['GroupItem']:
        parent = ensure.is_instance(parent, Authenticator)
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.groups.all().order_by('name')
            else:
                q = parent.groups.filter(uuid=process_uuid(item))
            res: list[GroupItem] = []
            i = None
            for i in q:
                val: GroupItem = {
                    'id': i.uuid,
                    'name': i.name,
                    'comments': i.comments,
                    'state': i.state,
                    'type': i.is_meta and 'meta' or 'group',
                    'meta_if_any': i.meta_if_any,
                    'skip_mfa': i.skip_mfa,
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
            result['pools'] = [v.uuid for v in get_service_pools_for_groups([i])]
            return result
        except Exception as e:
            logger.error('Group item not found: %s.%s: %s', parent.name, item, e)
            raise self.invalid_item_response() from e

    def get_title(self, parent: 'Model') -> str:
        parent = ensure.is_instance(parent, Authenticator)
        try:
            return _('Groups of {0}').format(parent.name)
        except Exception:
            return _('Current groups')

    def get_fields(self, parent: 'Model') -> list[typing.Any]:
        return [
            {
                'name': {
                    'title': _('Group'),
                }
            },
            {'comments': {'title': _('Comments')}},
            {
                'state': {
                    'title': _('state'),
                    'type': 'dict',
                    'dict': {State.ACTIVE: _('Enabled'), State.INACTIVE: _('Disabled')},
                }
            },
            {
                'skip_mfa': {
                    'title': _('Skip MFA'),
                    'type': 'dict',
                    'dict': {State.ACTIVE: _('Enabled'), State.INACTIVE: _('Disabled')},
                }
            },
        ]

    def get_types(
        self, parent: 'Model', for_type: typing.Optional[str]
    ) -> collections.abc.Iterable[types.rest.TypeInfoDict]:
        parent = ensure.is_instance(parent, Authenticator)
        types_dict: dict[str, dict[str, str]] = {
            'group': {'name': _('Group'), 'description': _('UDS Group')},
            'meta': {'name': _('Meta group'), 'description': _('UDS Meta Group')},
        }
        types_list: list[types.rest.TypeInfoDict] = [
            {
                'name': v['name'],
                'type': k,
                'description': v['description'],
                'icon': '',
            }
            for k, v in types_dict.items()
        ]

        if for_type is None:
            return types_list

        try:
            return [next(filter(lambda x: x['type'] == for_type, types_list))]
        except Exception:
            raise self.invalid_request_response() from None

    def save_item(self, parent: 'Model', item: typing.Optional[str]) -> typing.Any:
        parent = ensure.is_instance(parent, Authenticator)
        group = None  # Avoid warning on reference before assignment
        try:
            is_meta = self._params['type'] == 'meta'
            meta_if_any = self._params.get('meta_if_any', False)
            pools = self._params.get('pools', None)
            skip_check = self._params.get('skip_check', False)
            logger.debug('Saving group %s / %s', parent, item)
            logger.debug('Meta any %s', meta_if_any)
            logger.debug('Pools: %s', pools)
            logger.debug('Skip check: %s', skip_check)
            valid_fields = ['name', 'comments', 'state', 'skip_mfa']
            if self._params.get('name', '') == '':
                raise exceptions.rest.RequestError(_('Group name is required'))
            fields = self.fields_from_params(valid_fields)
            is_pattern = fields.get('name', '').find('pat:') == 0
            auth = parent.get_instance()
            to_save: dict[str, typing.Any] = {}
            if not item:  # Create new
                if not is_meta and not is_pattern and not skip_check:
                    auth.create_group(
                        fields
                    )  # this throws an exception if there is an error (for example, this auth can't create groups)
                for k in valid_fields:
                    to_save[k] = fields[k]
                to_save['comments'] = fields['comments'][:255]
                to_save['is_meta'] = is_meta
                to_save['meta_if_any'] = meta_if_any
                group = parent.groups.create(**to_save)
            else:
                if not is_meta and not is_pattern:
                    auth.modify_group(fields)
                for k in valid_fields:
                    to_save[k] = fields[k]
                del to_save['name']  # Name can't be changed
                to_save['comments'] = fields['comments'][:255]
                to_save['meta_if_any'] = meta_if_any
                to_save['skip_mfa'] = fields['skip_mfa']

                group = parent.groups.get(uuid=process_uuid(item))
                group.__dict__.update(to_save)

            if is_meta:
                # Do not allow to add meta groups to meta groups
                group.groups.set(
                    i for i in parent.groups.filter(uuid__in=self._params['groups']) if i.is_meta is False
                )

            if pools:
                # Update pools
                group.deployedServices.set(ServicePool.objects.filter(uuid__in=pools))

            group.save()
            return {'id': group.uuid}
        except Group.DoesNotExist:
            raise self.invalid_item_response() from None
        except IntegrityError:  # Duplicate key probably
            raise exceptions.rest.RequestError(_('User already exists (duplicate key error)')) from None
        except exceptions.auth.AuthenticatorException as e:
            raise exceptions.rest.RequestError(str(e)) from e
        except exceptions.rest.RequestError:  # pylint: disable=try-except-raise
            raise  # Re-raise
        except Exception as e:
            logger.exception('Saving group')
            raise self.invalid_request_response() from e

    def delete_item(self, parent: 'Model', item: str) -> None:
        parent = ensure.is_instance(parent, Authenticator)
        try:
            group = parent.groups.get(uuid=item)

            group.delete()
        except Exception:
            raise self.invalid_item_response() from None

    def services_pools(self, parent: 'Model', item: str) -> list[collections.abc.Mapping[str, typing.Any]]:
        parent = ensure.is_instance(parent, Authenticator)
        uuid = process_uuid(item)
        group = parent.groups.get(uuid=process_uuid(uuid))
        res: list[collections.abc.Mapping[str, typing.Any]] = []
        for i in get_service_pools_for_groups((group,)):
            res.append(
                {
                    'id': i.uuid,
                    'name': i.name,
                    'thumb': i.image.thumb64 if i.image is not None else consts.images.DEFAULT_THUMB_BASE64,
                    'user_services_count': i.userServices.exclude(
                        state__in=(State.REMOVED, State.ERROR)
                    ).count(),
                    'state': _('With errors') if i.is_restrained() else _('Ok'),
                }
            )

        return res

    def users(self, parent: 'Model', item: str) -> list[collections.abc.Mapping[str, typing.Any]]:
        uuid = process_uuid(item)
        parent = ensure.is_instance(parent, Authenticator)
        group = parent.groups.get(uuid=process_uuid(uuid))

        def info(user: 'User') -> dict[str, typing.Any]:
            return {
                'id': user.uuid,
                'name': user.name,
                'real_name': user.real_name,
                'state': user.state,
                'last_access': user.last_access,
            }

        if group.is_meta:
            # Get all users for everygroup and
            groups = get_groups_from_metagroup((group,))
            users_set: typing.Optional[set['User']] = None
            for g in groups:
                current_set: set['User'] = set((i for i in g.users.all()))
                if users_set is None:
                    users_set = current_set
                else:
                    if group.meta_if_any:
                        users_set |= current_set
                    else:
                        users_set &= current_set

                        if not users_set:
                            break  # If already empty, stop
            users = list(users_set or {}) if users_set else []
            users_set = None
        else:
            users = list(group.users.all())

        return [info(i) for i in users]
