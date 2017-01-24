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

# import time
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from uds.core.util.State import State

from uds.core.auths.Exceptions import AuthenticatorException
from uds.core.util import log
from uds.core.util.model import processUuid
from uds.models import Authenticator, User, Group
from uds.core.auths.User import User as aUser
from uds.core.managers import cryptoManager
from uds.REST import RequestError
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from .user_services import AssignedService

from uds.REST.model import DetailHandler

import logging

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
    for g in getGroupsFromMeta(groups):
        for servicePool in g.deployedServices.all():
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
                return list(Users.uuid_to_id(parent.users.all().values('uuid', 'name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin', 'last_access', 'parent')))
            else:
                u = parent.users.get(uuid=processUuid(item))
                res = model_to_dict(u, fields=('name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin', 'last_access', 'parent'))
                res['id'] = u.uuid
                usr = aUser(u)
                res['groups'] = [g.dbGroup().uuid for g in usr.groups()]
                logger.debug('Item: {0}'.format(res))
                return res
        except Exception:
            logger.exception('En users')
            self.invalidItemException()

    def getTitle(self, parent):
        try:
            return _('Users of {0}').format(Authenticator.objects.get(uuid=processUuid(self._kwargs['parent_id'])).name)
        except Exception:
            return _('Current users')

    def getFields(self, parent):
        return [
            {'name': {'title': _('Username'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-user text-success'}},
            {'real_name': {'title': _('Name')}},
            {'comments': {'title': _('Comments')}},
            {'state': {'title': _('state'), 'type': 'dict', 'dict': State.dictionary()}},
            {'last_access': {'title': _('Last access'), 'type': 'datetime'}},
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def getLogs(self, parent, item):
        try:
            user = parent.users.get(uuid=processUuid(item))
        except Exception:
            self.invalidItemException()

        return log.getLogs(user)

    def saveItem(self, parent, item):
        logger.debug('Saving user {0} / {1}'.format(parent, item))
        valid_fields = ['name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin']
        if 'password' in self._params:
            valid_fields.append('password')
            self._params['password'] = cryptoManager().hash(self._params['password'])

        fields = self.readFieldsFromParams(valid_fields)
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

            logger.debug('User parent: {}'.format(user.parent))
            if auth.isExternalSource is False and (user.parent is None or user.parent == ''):
                groups = self.readFieldsFromParams(['groups'])['groups']
                logger.debug('Groups: {}'.format(groups))
                logger.debug('Got Groups {}'.format(parent.groups.filter(uuid__in=groups)))
                user.groups = parent.groups.filter(uuid__in=groups)

            user.save()

        except User.DoesNotExist:
            self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(unicode(e))
        except ValidationError as e:
            raise RequestError(unicode(e.message))
        except Exception:
            logger.exception('Saving user')
            self.invalidRequestException()

        return self.getItems(parent, user.uuid)

    def deleteItem(self, parent, item):
        try:
            user = parent.users.get(uuid=processUuid(item))

            user.delete()
        except Exception:
            self.invalidItemException()

        return 'deleted'

    def servicesPools(self, parent, item):
        uuid = processUuid(item)
        user = parent.users.get(uuid=processUuid(uuid))
        res = []
        for i in getPoolsForGroups(user.groups.all()):
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
                    val['groups'] = list(x.uuid for x in i.groups.all())
                res.append(val)
            if multi:
                return res
            return res[0]
        except:
            logger.exception('REST groups')
            self.invalidItemException()

    def getTitle(self, parent):
        try:
            return _('Groups of {0}').format(Authenticator.objects.get(uuid=processUuid(self._kwargs['parent_id'])).name)
        except:
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
        } for t in tDct.keys()]
        if forType is None:
            return types
        else:
            try:
                return types[forType]
            except Exception:
                self.invalidRequestException()

    def saveItem(self, parent, item):
        try:
            is_meta = self._params['type'] == 'meta'
            meta_if_any = self._params.get('meta_if_any', False)
            logger.debug('Saving group {0} / {1}'.format(parent, item))
            logger.debug('Meta any {}'.format(meta_if_any))
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
                group.groups = parent.groups.filter(uuid__in=self._params['groups'])

            group.save()
        except Group.DoesNotExist:
            self.invalidItemException()
        except IntegrityError:  # Duplicate key probably
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(unicode(e))
        except Exception:
            logger.exception('Saving group')
            self.invalidRequestException()

        return self.getItems(parent, group.uuid)

    def deleteItem(self, parent, item):
        try:
            group = parent.groups.get(uuid=item)

            group.delete()
        except:
            self.invalidItemException()

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
        groups = getGroupsFromMeta((group,))

        res = []
        for group in groups:
            for i in group.users.all():
                res.append({
                    'id': i.uuid,
                    'name': i.name,
                    'real_name': i.real_name,
                    'state': i.state,
                    'last_access': i.last_access
                })

        return res
