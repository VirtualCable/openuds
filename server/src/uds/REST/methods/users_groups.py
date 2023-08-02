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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext as _
from django.forms.models import model_to_dict
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError

from uds.core.util.state import State

from uds.core.auths.exceptions import AuthenticatorException
from uds.core.auths.user import User as aUser
from uds.core.util import log
from uds.core.util.model import processUuid
from uds.models import Authenticator, User, Group, ServicePool
from uds.core.managers.crypto import CryptoManager
from uds.REST import RequestError
from uds.core.ui.images import DEFAULT_THUMB_BASE64

from uds.REST.model import DetailHandler

from .user_services import AssignedService


logger = logging.getLogger(__name__)

# Details of /auth

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.models import UserService


def getGroupsFromMeta(groups):
    for g in groups:
        if g.is_meta:
            for x in g.groups.all():
                yield x
        else:
            yield g


def getPoolsForGroups(groups):
    for servicePool in ServicePool.getDeployedServicesForGroups(groups):
        yield servicePool


class Users(DetailHandler):
    custom_methods = ['servicesPools', 'userServices', 'cleanRelated']

    def getItems(self, parent: Authenticator, item: typing.Optional[str]):
        # processes item to change uuid key for id
        def uuid_to_id(
            iterable: typing.Iterable[typing.MutableMapping[str, typing.Any]]
        ):
            for v in iterable:
                v['id'] = v['uuid']
                del v['uuid']
                yield v

        logger.debug(item)
        # Extract authenticator
        try:
            if item is None:
                values = list(
                    uuid_to_id(
                        (
                            i
                            for i in parent.users.all().values(
                                'uuid',
                                'name',
                                'real_name',
                                'comments',
                                'state',
                                'staff_member',
                                'is_admin',
                                'last_access',
                                'parent',
                                'mfa_data',
                            )
                        )
                    )
                )
                for res in values:
                    res['role'] = (
                        res['staff_member']
                        and (res['is_admin'] and _('Admin') or _('Staff member'))
                        or _('User')
                    )
                return values
            u = parent.users.get(uuid=processUuid(item))
            res = model_to_dict(
                u,
                fields=(
                    'name',
                    'real_name',
                    'comments',
                    'state',
                    'staff_member',
                    'is_admin',
                    'last_access',
                    'parent',
                    'mfa_data',
                ),
            )
            res['id'] = u.uuid
            res['role'] = (
                res['staff_member']
                and (res['is_admin'] and _('Admin') or _('Staff member'))
                or _('User')
            )
            usr = aUser(u)
            res['groups'] = [g.dbGroup().uuid for g in usr.groups()]
            logger.debug('Item: %s', res)
            return res
        except Exception as e:
            logger.exception('En users')
            raise self.invalidItemException() from e

    def getTitle(self, parent):
        try:
            return _('Users of {0}').format(
                Authenticator.objects.get(
                    uuid=processUuid(self._kwargs['parent_id'])
                ).name
            )
        except Exception:
            return _('Current users')

    def getFields(self, parent: Authenticator):
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
                    'dict': State.dictionary(),
                }
            },
            {'last_access': {'title': _('Last access'), 'type': 'datetime'}},
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def getLogs(self, parent: Authenticator, item: str):
        user = None
        try:
            user = parent.users.get(uuid=processUuid(item))
        except Exception:
            raise self.invalidItemException() from None

        return log.getLogs(user)

    def saveItem(self, parent: Authenticator, item):
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
            raise RequestError(_('Username cannot be empty'))

        if 'password' in self._params:
            valid_fields.append('password')
            self._params['password'] = CryptoManager().hash(self._params['password'])

        if 'mfa_data' in self._params:
            valid_fields.append('mfa_data')
            self._params['mfa_data'] = self._params['mfa_data'].strip()

        fields = self.readFieldsFromParams(valid_fields)
        if not self._user.is_admin:
            del fields['staff_member']
            del fields['is_admin']

        user = None
        try:
            with transaction.atomic():
                auth = parent.getInstance()
                if item is None:  # Create new
                    auth.createUser(
                        fields
                    )  # this throws an exception if there is an error (for example, this auth can't create users)
                    user = parent.users.create(**fields)
                else:
                    auth.modifyUser(fields)  # Notifies authenticator
                    user = parent.users.get(uuid=processUuid(item))
                    user.__dict__.update(fields)
                    user.save()

                logger.debug('User parent: %s', user.parent)
                # If internal auth, and not a child user, save groups
                if not auth.isExternalSource and not user.parent:
                    groups = self.readFieldsFromParams(['groups'])['groups']
                    # Save but skip meta groups, they are not real groups, but just a way to group users based on rules
                    user.groups.set(
                        g
                        for g in parent.groups.filter(uuid__in=groups)
                        if g.is_meta is False
                    )
        except User.DoesNotExist:
            raise self.invalidItemException() from None
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)')) from None
        except AuthenticatorException as e:
            raise RequestError(str(e)) from e
        except ValidationError as e:
            raise RequestError(str(e.message)) from e
        except RequestError:  # pylint: disable=try-except-raise
            raise  # Re-raise
        except Exception as e:
            logger.exception('Saving user')
            raise self.invalidRequestException() from e

        return self.getItems(parent, user.uuid)

    def deleteItem(self, parent: Authenticator, item: str):
        try:
            user = parent.users.get(uuid=processUuid(item))
            if not self._user.is_admin and (user.is_admin or user.staff_member):
                logger.warning(
                    'Removal of user %s denied due to insufficients rights',
                    user.pretty_name,
                )
                raise self.invalidItemException(
                    f'Removal of user {user.pretty_name} denied due to insufficients rights'
                )

            assignedUserService: 'UserService'
            for assignedUserService in user.userServices.all():
                try:
                    assignedUserService.user = None  # type: ignore  # Remove assigned user (avoid cascade deletion)
                    assignedUserService.save(update_fields=['user'])
                    assignedUserService.removeOrCancel()
                except Exception:
                    logger.exception('Removing user service')
                    try:
                        assignedUserService.save()
                    except Exception:
                        logger.exception('Saving user on removing error')

            user.delete()
        except Exception as e:
            logger.exception('Removing user')
            raise self.invalidItemException() from e

        return 'deleted'

    def servicesPools(self, parent: Authenticator, item: str):
        uuid = processUuid(item)
        user = parent.users.get(uuid=processUuid(uuid))
        res = []
        groups = list(user.getGroups())
        for i in getPoolsForGroups(groups):
            res.append(
                {
                    'id': i.uuid,
                    'name': i.name,
                    'thumb': i.image.thumb64
                    if i.image is not None
                    else DEFAULT_THUMB_BASE64,
                    'user_services_count': i.userServices.exclude(
                        state__in=(State.REMOVED, State.ERROR)
                    ).count(),
                    'state': _('With errors') if i.isRestrained() else _('Ok'),
                }
            )

        return res

    def userServices(self, parent: Authenticator, item: str):
        uuid = processUuid(item)
        user = parent.users.get(uuid=processUuid(uuid))
        res = []
        for i in user.userServices.all():
            if i.state == State.USABLE:
                v = AssignedService.itemToDict(i)
                v['pool'] = i.deployed_service.name
                v['pool_id'] = i.deployed_service.uuid
                res.append(v)

        return res

    def cleanRelated(self, parent: Authenticator, item: str) -> typing.Dict:
        uuid = processUuid(item)
        user = parent.users.get(uuid=processUuid(uuid))
        user.cleanRelated()
        return {'status': 'ok'}


class Groups(DetailHandler):
    custom_methods = ['servicesPools', 'users']

    def getItems(self, parent: Authenticator, item: typing.Optional[str]):
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
                    val['groups'] = list(
                        x.uuid for x in i.groups.all().order_by('name')
                    )
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

    def getTitle(self, parent: Authenticator) -> str:
        try:
            return _('Groups of {0}').format(parent.name)
        except Exception:
            return _('Current groups')

    def getFields(self, parent):
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
                    'dict': State.dictionary(),
                }
            },
        ]

    def getTypes(self, parent: Authenticator, forType: typing.Optional[str]):
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

    def saveItem(self, parent: Authenticator, item: typing.Optional[str]) -> None:
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
                    i
                    for i in parent.groups.filter(uuid__in=self._params['groups'])
                    if i.is_meta is False
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

    def deleteItem(self, parent: Authenticator, item: str) -> None:
        try:
            group = parent.groups.get(uuid=item)

            group.delete()
        except Exception:
            raise self.invalidItemException() from None

    def servicesPools(
        self, parent: Authenticator, item: str
    ) -> typing.List[typing.Mapping[str, typing.Any]]:
        uuid = processUuid(item)
        group = parent.groups.get(uuid=processUuid(uuid))
        res: typing.List[typing.Mapping[str, typing.Any]] = []
        for i in getPoolsForGroups((group,)):
            res.append(
                {
                    'id': i.uuid,
                    'name': i.name,
                    'thumb': i.image.thumb64
                    if i.image is not None
                    else DEFAULT_THUMB_BASE64,
                    'user_services_count': i.userServices.exclude(
                        state__in=(State.REMOVED, State.ERROR)
                    ).count(),
                    'state': _('With errors') if i.isRestrained() else _('Ok'),
                }
            )

        return res

    def users(
        self, parent: Authenticator, item: str
    ) -> typing.List[typing.Mapping[str, typing.Any]]:
        uuid = processUuid(item)
        group = parent.groups.get(uuid=processUuid(uuid))

        def info(user):
            return {
                'id': user.uuid,
                'name': user.name,
                'real_name': user.real_name,
                'state': user.state,
                'last_access': user.last_access,
            }

        if group.is_meta:
            # Get all users for everygroup and
            groups = getGroupsFromMeta((group,))
            tmpSet: typing.Optional[typing.Set] = None
            for g in groups:
                gSet = set((i for i in g.users.all()))
                if tmpSet is None:
                    tmpSet = gSet
                else:
                    if group.meta_if_any:
                        tmpSet |= gSet
                    else:
                        tmpSet &= gSet

                        if not tmpSet:
                            break  # If already empty, stop
            users = list(tmpSet or {}) if tmpSet else []
            tmpSet = None
        else:
            users = group.users.all()

        return [info(i) for i in users]
