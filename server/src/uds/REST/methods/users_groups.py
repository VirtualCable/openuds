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

from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from uds.core.util.state import State

from uds.core.auths.exceptions import AuthenticatorException
from uds.core.auths.user import User as aUser
from uds.core.util import log
from uds.core.util.model import processUuid
from uds.models import Authenticator, User, Group, ServicePool
from uds.core.managers import cryptoManager
from uds.REST import RequestError
from uds.core.ui.images import DEFAULT_THUMB_BASE64

from uds.REST.model import DetailHandler

from .user_services import AssignedService


logger = logging.getLogger(__name__)

# Details of /auth


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

    custom_methods = ['servicesPools', 'userServices']

    @staticmethod
    def uuid_to_id(iterator):
        for v in iterator:
            v['id'] = v['uuid']
            del v['uuid']
            yield v

    def getItems(self, parent, item):
        logger.debug(item)
        # Extract authenticator
        try:
            if item is None:
                values = list(Users.uuid_to_id(parent.users.all().values('uuid', 'name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin', 'last_access', 'parent')))
                for res in values:
                    res['role'] = res['staff_member'] and (res['is_admin'] and _('Admin') or _('Staff member')) or _('User')
                return values
            else:
                u = parent.users.get(uuid=processUuid(item))
                res = model_to_dict(u, fields=('name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin', 'last_access', 'parent'))
                res['id'] = u.uuid
                res['role'] = res['staff_member'] and (res['is_admin'] and _('Admin') or _('Staff member')) or _('User')
                usr = aUser(u)
                res['groups'] = [g.dbGroup().uuid for g in usr.groups()]
                logger.debug('Item: %s', res)
                return res
        except Exception:
            logger.exception('En users')
            raise self.invalidItemException()

    def getTitle(self, parent):
        try:
            return _('Users of {0}').format(Authenticator.objects.get(uuid=processUuid(self._kwargs['parent_id'])).name)
        except Exception:
            return _('Current users')

    def getFields(self, parent):
        return [
            {'name': {'title': _('Username'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-user text-success'}},
            {'role': {'title': _('Role')}},
            {'real_name': {'title': _('Name')}},
            {'comments': {'title': _('Comments')}},
            {'state': {'title': _('state'), 'type': 'dict', 'dict': State.dictionary()}},
            {'last_access': {'title': _('Last access'), 'type': 'datetime'}},
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def getLogs(self, parent, item):
        user = None
        try:
            user = parent.users.get(uuid=processUuid(item))
        except Exception:
            raise self.invalidItemException()

        return log.getLogs(user)

    def saveItem(self, parent, item):
        logger.debug('Saving user %s / %s', parent, item)
        valid_fields = ['name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin']
        if 'password' in self._params:
            valid_fields.append('password')
            self._params['password'] = cryptoManager().hash(self._params['password'])

        fields = self.readFieldsFromParams(valid_fields)
        if not self._user.is_admin:
            del fields['staff_member']
            del fields['is_admin']

        user = None
        try:
            auth = parent.getInstance()
            if item is None:  # Create new
                auth.createUser(fields)  # this throws an exception if there is an error (for example, this auth can't create users)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                user = parent.users.create(**toSave)
            else:
                auth.modifyUser(fields)  # Notifies authenticator
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                user = parent.users.get(uuid=processUuid(item))
                user.__dict__.update(toSave)

            logger.debug('User parent: %s', user.parent)
            if auth.isExternalSource is False and (user.parent is None or user.parent == ''):
                groups = self.readFieldsFromParams(['groups'])['groups']
                logger.debug('Groups: %s', groups)
                logger.debug('Got Groups %s', parent.groups.filter(uuid__in=groups))
                user.groups.set(parent.groups.filter(uuid__in=groups))

            user.save()

        except User.DoesNotExist:
            raise self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(str(e))
        except ValidationError as e:
            raise RequestError(str(e.message))
        except Exception:
            logger.exception('Saving user')
            raise self.invalidRequestException()

        return self.getItems(parent, user.uuid)

    def deleteItem(self, parent, item):
        try:
            user = parent.users.get(uuid=processUuid(item))
            if not self._user.is_admin and (user.is_admin or user.staff_member):
                logger.warn('Removal of user {} denied due to insufficients rights')
                raise self.invalidItemException('Removal of user {} denied due to insufficients rights')

            for us in user.userServices.all():
                try:
                    us.user = None
                    us.removeOrCancel()
                except Exception:
                    logger.exception('Removing user service')
                    try:
                        us.save()
                    except Exception:
                        logger.exception('Saving user on removing error')

            user.delete()
        except Exception:
            logger.exception('Removing user')
            raise self.invalidItemException()

        return 'deleted'

    def servicesPools(self, parent, item):
        uuid = processUuid(item)
        user = parent.users.get(uuid=processUuid(uuid))
        res = []
        groups = list(user.getGroups())
        for i in getPoolsForGroups(groups):
            res.append({
                'id': i.uuid,
                'name': i.name,
                'thumb': i.image.thumb64 if i.image is not None else DEFAULT_THUMB_BASE64,
                'user_services_count': i.userServices.exclude(state__in=(State.REMOVED, State.ERROR)).count(),
                'state': _('With errors') if i.isRestrained() else _('Ok'),
            })

        return res

    def userServices(self, parent, item):
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


class Groups(DetailHandler):

    custom_methods = ['servicesPools', 'users']

    def getItems(self, parent, item):
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
                    'meta_if_any': i.meta_if_any
                }
                if i.is_meta:
                    val['groups'] = list(x.uuid for x in i.groups.all().order_by('name'))
                res.append(val)
            if multi or not i:
                return res
            # Add pools field if 1 item only
            res = res[0]
            if i.is_meta:
                res['pools'] = []  # Meta groups do not have "assigned "pools, they get it from groups interaction
            else:
                res['pools'] = [v.uuid for v in  i.deployedServices.all()]
            return res
        except Exception:
            logger.exception('REST groups')
            raise self.invalidItemException()

    def getTitle(self, parent):
        try:
            return _('Groups of {0}').format(Authenticator.objects.get(uuid=processUuid(self._kwargs['parent_id'])).name)
        except Exception:
            return _('Current groups')

    def getFields(self, parent):
        return [
            {'name': {'title': _('Group'), 'visible': True, 'type': 'icon_dict', 'icon_dict': {'group': 'fa fa-group text-success', 'meta': 'fa fa-gears text-info'}}},
            {'comments': {'title': _('Comments')}},
            {'state': {'title': _('state'), 'type': 'dict', 'dict': State.dictionary()}},
        ]

    def getTypes(self, parent, forType):
        tDct = {
            'group': {'name': _('Group'), 'description': _('UDS Group')},
            'meta': {'name': _('Meta group'), 'description': _('UDS Meta Group')},
        }
        types = [{
            'name': tDct[t]['name'],
            'type': t,
            'description': tDct[t]['description'],
            'icon': ''
        } for t in tDct]

        if forType is None:
            return types

        try:
            return types[forType]
        except Exception:
            raise self.invalidRequestException()

    def saveItem(self, parent, item):
        group = None  # Avoid warning on reference before assignment
        try:
            is_meta = self._params['type'] == 'meta'
            meta_if_any = self._params.get('meta_if_any', False)
            pools = self._params.get('pools', None)
            logger.debug('Saving group %s / %s', parent, item)
            logger.debug('Meta any %s', meta_if_any)
            logger.debug('Pools: %s', pools)
            valid_fields = ['name', 'comments', 'state']
            fields = self.readFieldsFromParams(valid_fields)
            is_pattern = fields.get('name', '').find('pat:') == 0
            auth = parent.getInstance()
            if item is None:  # Create new
                if not is_meta and not is_pattern:
                    auth.createGroup(fields)  # this throws an exception if there is an error (for example, this auth can't create groups)
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
                group.groups.set(parent.groups.filter(uuid__in=self._params['groups']))

            if pools:
                # Update pools
                group.deployedServices.set(ServicePool.objects.filter(uuid__in=pools))

            group.save()
        except Group.DoesNotExist:
            raise self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(str(e))
        except Exception:
            logger.exception('Saving group')
            raise self.invalidRequestException()

        return self.getItems(parent, group.uuid)

    def deleteItem(self, parent, item):
        try:
            group = parent.groups.get(uuid=item)

            group.delete()
        except Exception:
            raise self.invalidItemException()

        return 'deleted'

    def servicesPools(self, parent, item):
        uuid = processUuid(item)
        group = parent.groups.get(uuid=processUuid(uuid))
        res = []
        for i in getPoolsForGroups((group,)):
            res.append({
                'id': i.uuid,
                'name': i.name,
                'thumb': i.image.thumb64 if i.image is not None else DEFAULT_THUMB_BASE64,
                'user_services_count': i.userServices.exclude(state__in=(State.REMOVED, State.ERROR)).count(),
                'state': _('With errors') if i.isRestrained() else _('Ok'),
            })

        return res

    def users(self, parent, item):
        uuid = processUuid(item)
        group = parent.groups.get(uuid=processUuid(uuid))

        def info(user):
            return {
                'id': user.uuid,
                'name': user.name,
                'real_name': user.real_name,
                'state': user.state,
                'last_access': user.last_access
            }

        res = []
        if group.is_meta:
            # Get all users for everygroup and
            groups = getGroupsFromMeta((group,))
            tmpSet = None
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
            users = list(tmpSet)
            tmpSet = None
        else:
            users = group.users.all()

        for i in users:
            res.append(info(i))

        return res
