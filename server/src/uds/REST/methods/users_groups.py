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

#import time
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict
from uds.core.util.State import State
from django.db import IntegrityError

from uds.core.auths.Exceptions import AuthenticatorException
from uds.core.util import log
from uds.models import Authenticator, User, Group
from uds.core.auths.User import User as aUser
from uds.REST import RequestError

from uds.REST.model import DetailHandler

import logging

logger = logging.getLogger(__name__)

# Details of /auth

class Users(DetailHandler):
    
    def getItems(self, parent, item):
        # Extract authenticator
        try:
            if item is None:
                return list(parent.users.all().values('id','name','real_name','comments','state','staff_member','is_admin','last_access','parent'))
            else:
                u = parent.users.get(pk=item)
                res = model_to_dict(u, fields = ('id','name','real_name','comments','state','staff_member','is_admin','last_access','parent'))
                usr = aUser(u)
                res['groups'] = [g.dbGroup().id for g in usr.groups()]
                logger.debug('Item: {0}'.format(res))
                return res
        except:
            logger.exception('En users')
            self.invalidItemException()
        
    def getTitle(self, parent):
        try:
            return _('Users of {0}').format(Authenticator.objects.get(pk=self._kwargs['parent_id']).name)
        except:
            return _('Current users')
    
    def getFields(self, parent):
        return [
            { 'name': {'title': _('Username'), 'visible': True, 'type': 'icon', 'icon': 'fa fa-user text-success' } },
            { 'real_name': { 'title': _('Name') } },
            { 'comments': { 'title': _('Comments') } },
            { 'state': { 'title': _('state'), 'type': 'dict', 'dict': State.dictionary() } },
            { 'last_access': { 'title': _('Last access'), 'type': 'datetime' } },
        ]
        
    def getRowStyle(self, parent):
        return  { 'field': 'state', 'prefix': 'row-state-' }
        
    def getLogs(self, parent, item):
        try:
            user = parent.users.get(pk=item)
        except:
            self.invalidItemException()
            
        return log.getLogs(user)

    def saveItem(self, parent, item):
        # Extract item db fields
        # We need this fields for all
        logger.debug('Saving user {0} / {1}'.format(parent, item))
        valid_fields = ['name', 'real_name', 'comments', 'state', 'staff_member', 'is_admin']
        fields = self.readFieldsFromParams(valid_fields + ['groups'])
        try:
            auth = parent.getInstance()
            groups = fields['groups']
            del fields['groups'] # Not update this on user dict
            if item is None: # Create new
                auth.createUser(fields) # this throws an exception if there is an error (for example, this auth can't create users)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                user = parent.users.create(**toSave)
            else:
                auth.modifyUser(fields) # Notifies authenticator
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                user = parent.users.get(pk=item)
                user.__dict__.update(toSave)
                
            if auth.isExternalSource == False and user.parent == -1:
                user.groups = Group.objects.filter(id__in=groups)
                
            user.save()
            
        except User.DoesNotExist: 
            self.invalidItemException()
        except IntegrityError: # Duplicate key probably 
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(unicode(e))
        except Exception:
            logger.exception('Saving user')
            self.invalidRequestException()
        
        return self.getItems(parent, user.id)
    
    def deleteItem(self, parent, item):
        try:
            user = parent.users.get(pk=item)
            
            user.delete()
        except:
            self.invalidItemException()
        
        return 'deleted'

class Groups(DetailHandler):
    
    def getItems(self, parent, item):
        # Extract authenticator
        try:
            multi = False
            if item is None:
                multi = True
                q = parent.groups.all()
            else:
                q = parent.groups.filter(pk=item)
            res = []
            for i in q:
                val = {
                    'id': i.id,
                    'name': i.name,
                    'comments': i.comments,
                    'state': i.state,
                    'type': i.is_meta and 'meta' or 'group'
                }
                if i.is_meta:
                    val['groups'] = list(x.id for x in i.groups.all())
                res.append(val)
            if multi:
                return res
            return res[0]
        except:
            logger.exception('REST groups')
            self.invalidItemException()
        
    def getTitle(self, parent):
        try:
            return _('Groups of {0}').format(Authenticator.objects.get(pk=self._kwargs['parent_id']).name)
        except:
            return _('Current groups')
    
    def getFields(self, parent):
        return [
            { 'name': {'title': _('Group'), 'visible': True, 'type': 'icon_dict', 'icon_dict': {'group' : 'fa fa-group text-success', 'meta' : 'fa fa-gears text-info' } } },
            { 'comments': { 'title': _('Comments') } },
            { 'state': { 'title': _('state'), 'type': 'dict', 'dict': State.dictionary() } },
        ]        
    
    def getTypes(self, parent, forType):
        tDct = {
            'group': { 'name': _('Group'), 'description': _('UDS Group') },
            'meta' : { 'name': _('Meta group'), 'description': _('UDS Meta Group') },
        }
        types = [{ 
            'name' : tDct[t]['name'], 
            'type' : t, 
            'description' : tDct[t]['description'], 
            'icon' : '' } for t in tDct.keys()]
        if forType is None:
            return types
        else:
            try:
                return types[forType]
            except:
                self.invalidRequestException()

    def saveItem(self, parent, item):
        try:
            is_meta = self._params['type'] == 'meta'
            logger.debug('Saving group {0} / {1}'.format(parent, item))
            valid_fields = ['name', 'comments', 'state']
            fields = self.readFieldsFromParams(valid_fields)
            auth = parent.getInstance()
            if item is None: # Create new
                if not is_meta:
                    auth.createGroup(fields) # this throws an exception if there is an error (for example, this auth can't create users)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                toSave['is_meta'] = is_meta
                group = parent.groups.create(**toSave)
            else:
                if not is_meta:
                    auth.modifyGroup(fields)
                toSave = {}
                for k in valid_fields:
                    toSave[k] = fields[k]
                del toSave['name'] # Name can't be changed
                group = parent.groups.get(pk=item)
                group.__dict__.update(toSave)
                
            if is_meta:
                group.groups = self._params['groups']
                    
            group.save()
        except Group.DoesNotExist: 
            self.invalidItemException()
        except IntegrityError: # Duplicate key probably 
            raise RequestError(_('User already exists (duplicate key error)'))
        except AuthenticatorException as e:
            raise RequestError(unicode(e))
        except Exception:
            logger.exception('Saving group')
            self.invalidRequestException()
        
        return self.getItems(parent, group.id)

    def deleteItem(self, parent, item):
        try:
            group = parent.groups.get(pk=item)
            
            group.delete()
        except:
            self.invalidItemException()
        
        return 'deleted'
