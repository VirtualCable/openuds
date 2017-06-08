# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

# pylint: disable=too-many-public-methods

from __future__ import unicode_literals

from django.utils.translation import ugettext as _


from uds.models import Group, Transport, DeployedServicePublication
from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.REST.model import DetailHandler
from uds.REST import ResponseError
from uds.core.util import permissions



import logging

logger = logging.getLogger(__name__)


class AssignedService(DetailHandler):
    '''
    Rest handler for Assigned Services, wich parent is Service
    '''

    @staticmethod
    def itemToDict(item, is_cache=False):
        '''
        Converts an assigned/cached service db item to a dictionary for REST response
        :param item: item to convert
        :param is_cache: If item is from cache or not
        '''
        props = item.getProperties()

        val = {
            'id': item.uuid,
            'id_deployed_service': item.deployed_service.uuid,
            'unique_id': item.unique_id,
            'friendly_name': item.friendly_name,
            'state': item.state,
            'os_state': item.os_state,
            'state_date': item.state_date,
            'creation_date': item.creation_date,
            'revision': item.publication and item.publication.revision or '',
            'ip': props.get('ip', _('unknown')),
            'actor_version': props.get('actor_version', _('unknown')),
        }

        if is_cache:
            val['cache_level'] = item.cache_level
        else:
            if item.user is None:
                owner = ''
                owner_info = {
                   'auth_id': '',
                   'user_id': ''
                }
            else:
                owner = item.user.pretty_name
                owner_info = {
                   'auth_id': item.user.manager.uuid,
                   'user_id': item.user.uuid
                }

            val.update({
                'owner': owner,
                'owner_info': owner_info,
                'in_use': item.in_use,
                'in_use_date': item.in_use_date,
                'source_host': item.src_hostname,
                'source_ip': item.src_ip
            })
        return val

    def getItems(self, parent, item):
        # Extract provider
        try:
            if item is None:
                return [AssignedService.itemToDict(k) for k in parent.assignedUserServices().all()
                        .prefetch_related('properties').prefetch_related('deployed_service').prefetch_related('publication')]
            else:
                return parent.assignedUserServices().get(processUuid(uuid=processUuid(item)))
        except Exception:
            logger.exception('getItems')
            self.invalidItemException()

    def getTitle(self, parent):
        return _('Assigned services')

    def getFields(self, parent):
        return [
            {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
            {'revision': {'title': _('Revision')}},
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {'state': {'title': _('status'), 'type': 'dict', 'dict': State.dictionary()}},
            {'state_date': {'title': _('Status date'), 'type': 'datetime'}},
            {'in_use': {'title': _('In Use')}},
            {'source_host': {'title': _('Src Host')}},
            {'source_ip': {'title': _('Src Ip')}},
            {'owner': {'title': _('Owner')}},
            {'actor_version': {'title': _('Actor version')}}
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def getLogs(self, parent, item):
        try:
            item = parent.assignedUserServices().get(uuid=processUuid(item))
            logger.debug('Getting logs for {0}'.format(item))
            return log.getLogs(item)
        except Exception:
            self.invalidItemException()

    def deleteItem(self, parent, item):  # This is also used by CachedService, so we use "userServices" directly and is valid for both
        try:
            service = parent.userServices.get(uuid=processUuid(item))
        except Exception:
            logger.exception('deleteItem')
            self.invalidItemException()

        logger.debug('Deleting assigned service')
        if service.state in (State.USABLE, State.REMOVING):
            service.remove()
        elif service.state == State.PREPARING:
            service.cancel()
        elif service.state == State.REMOVABLE:
            self.invalidItemException(_('Item already being removed'))
        else:
            self.invalidItemException(_('Item is not removable'))

        return self.success()


class CachedService(AssignedService):
    '''
    Rest handler for Cached Services, wich parent is Service
    '''

    def getItems(self, parent, item):
        # Extract provider
        try:
            if item is None:
                return [AssignedService.itemToDict(k, True) for k in parent.cachedUserServices().all()
                        .prefetch_related('properties').prefetch_related('deployed_service').prefetch_related('publication')]
            else:
                k = parent.cachedUserServices().get(uuid=processUuid(item))
                return AssignedService.itemToDict(k, True)
        except Exception:
            logger.exception('getItems')
            self.invalidItemException()

    def getTitle(self, parent):
        return _('Cached services')

    def getFields(self, parent):
        return [
            {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
            {'revision': {'title': _('Revision')}},
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {'state': {'title': _('State'), 'type': 'dict', 'dict': State.dictionary()}},
            {'cache_level': {'title': _('Cache level')}},
            {'actor_version': {'title': _('Actor version')}}
        ]

    def getLogs(self, parent, item):
        try:
            item = parent.cachedUserServices().get(uuid=processUuid(item))
            logger.debug('Getting logs for {0}'.format(item))
            return log.getLogs(item)
        except Exception:
            self.invalidItemException()


class Groups(DetailHandler):
    '''
    Processes the groups detail requests of a Service Pool
    '''
    def getItems(self, parent, item):
        return [{
            'id': i.uuid,
            'auth_id': i.manager.uuid,
            'name': i.name,
            'comments': i.comments,
            'state': i.state,
            'type': i.is_meta and 'meta' or 'group',
            'auth_name': i.manager.name,
        } for i in parent.assignedGroups.all()]

    def getTitle(self, parent):
        return _('Assigned groups')

    def getFields(self, parent):
        return [
            # Note that this field is "self generated" on client table
            {'group_name': {'title': _('Name'), 'type': 'icon_dict', 'icon_dict': {'group': 'fa fa-group text-success', 'meta': 'fa fa-gears text-info'}}},
            {'comments': {'title': _('comments')}},
            {'state': {'title': _('State'), 'type': 'dict', 'dict': State.dictionary()}},
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def saveItem(self, parent, item):
        parent.assignedGroups.add(Group.objects.get(uuid=processUuid(self._params['id'])))
        return self.success()

    def deleteItem(self, parent, item):
        parent.assignedGroups.remove(Group.objects.get(uuid=processUuid(self._args[0])))


class Transports(DetailHandler):
    '''
    Processes the transports detail requests of a Service Pool
    '''
    def getItems(self, parent, item):
        return [{
            'id': i.uuid,
            'name': i.name,
            'type': self.typeAsDict(i.getType()),
            'comments': i.comments,
            'priority': i.priority,
        } for i in parent.transports.all()]

    def getTitle(self, parent):
        return _('Assigned transports')

    def getFields(self, parent):
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'name': {'title': _('Name')}},
            {'trans_type': {'title': _('Type')}},
            {'comments': {'title': _('Comments')}},
        ]

    def saveItem(self, parent, item):
        parent.transports.add(Transport.objects.get(uuid=processUuid(self._params['id'])))
        return self.success()

    def deleteItem(self, parent, item):
        parent.transports.remove(Transport.objects.get(uuid=processUuid(self._args[0])))


class Publications(DetailHandler):
    '''
    Processes the publications detail requests of a Service Pool
    '''
    custom_methods = ['publish', 'cancel']  # We provided these custom methods

    def publish(self, parent):
        '''
        Custom method "publish", provided to initiate a publication of a deployed service
        :param parent: Parent service pool
        '''
        changeLog = self._params['changelog'] if 'changelog' in self._params else None

        if permissions.checkPermissions(self._user, parent, permissions.PERMISSION_MANAGEMENT) is False:
            logger.debug('Management Permission failed for user {}'.format(self._user))
            self.accessDenied()

        logger.debug('Custom "publish" invoked for {}'.format(parent))
        parent.publish(changeLog)  # Can raise exceptions that will be processed on response
        return self.success()

    def cancel(self, parent, uuid):
        '''
        Invoked to cancel a running publication
        Double invocation (this means, invoking cancel twice) will mean that is a "forced cancelation"
        :param parent: Parent service pool
        :param uuid: uuid of the publication
        '''
        if permissions.checkPermissions(self._user, parent, permissions.PERMISSION_MANAGEMENT) is False:
            logger.debug('Management Permission failed for user {}'.format(self._user))
            self.accessDenied()

        try:
            ds = DeployedServicePublication.objects.get(uuid=processUuid(uuid))
            ds.cancel()
        except Exception as e:
            raise ResponseError(unicode(e))

        return self.success()

    def getItems(self, parent, item):
        return [{
            'id': i.uuid,
            'revision': i.revision,
            'publish_date': i.publish_date,
            'state': i.state,
            'reason': State.isErrored(i.state) and i.getInstance().reasonOfError() or '',
            'state_date': i.state_date,
        } for i in parent.publications.all()]

    def getTitle(self, parent):
        return _('Publications')

    def getFields(self, parent):
        return [
            {'revision': {'title': _('Revision'), 'type': 'numeric', 'width': '6em'}},
            {'publish_date': {'title': _('Publish date'), 'type': 'datetime'}},
            {'state': {'title': _('State'), 'type': 'dict', 'dict': State.dictionary()}},
            {'reason': {'title': _('Reason')}},
        ]

    def getRowStyle(self, parent):
        return  {
            'field': 'state',
            'prefix': 'row-state-'
        }


class Changelog(DetailHandler):
    '''
    Processes the transports detail requests of a Service Pool
    '''
    def getItems(self, parent, item):
        return [{
            'revision': i.revision,
            'stamp': i.stamp,
            'log': i.log,
        } for i in parent.changelog.all()]

    def getTitle(self, parent):
        return _('Changelog')

    def getFields(self, parent):
        return [
            {'revision': {'title': _('Revision'), 'type': 'numeric', 'width': '6em'}},
            {'stamp': {'title': _('Publish date'), 'type': 'datetime'}},
            {'log': {'title': _('Comment')}},
        ]
