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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

# pylint: disable=too-many-public-methods

from __future__ import unicode_literals

from django.utils.translation import ugettext as _

from uds.models import UserService
from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.REST.model import DetailHandler

import logging

logger = logging.getLogger(__name__)


class ServicesUsage(DetailHandler):
    """
    Rest handler for Assigned Services, which parent is Service
    """

    @staticmethod
    def itemToDict(item):
        """
        Converts an assigned/cached service db item to a dictionary for REST response
        :param item: item to convert
        :param is_cache: If item is from cache or not
        """
        props = item.getProperties()

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

        return {
            'id': item.uuid,
            'state_date': item.state_date,
            'creation_date': item.creation_date,
            'unique_id': item.unique_id,
            'friendly_name': item.friendly_name,
            'owner': owner,
            'owner_info': owner_info,
            'service': item.deployed_service.service.name,
            'service_id': item.deployed_service.service.uuid,
            'pool': item.deployed_service.name,
            'pool_id': item.deployed_service.uuid,
            'ip': props.get('ip', _('unknown')),
            'source_host': item.src_hostname,
            'source_ip': item.src_ip,
            'in_use': item.in_use
        }

    def getItems(self, parent, item):
        try:
            if item is None:
                userServicesQuery = UserService.objects.filter(deployed_service__service__provider=parent)
            else:
                userServicesQuery = UserService.objects.filter(deployed_service__service_uuid=processUuid(item))

            return [ServicesUsage.itemToDict(k) for k in userServicesQuery.filter(state=State.USABLE).order_by('creation_date').
                    prefetch_related('deployed_service').prefetch_related('deployed_service__service').prefetch_related('properties')]

        except Exception:
            logger.exception('getItems')
            self.invalidItemException()

    def getTitle(self, parent):
        return _('Services Usage')

    def getFields(self, parent):
        return [
            # {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
            {'state_date': {'title': _('Access'), 'type': 'datetime'}},
            {'owner': {'title': _('Owner')}},
            {'service': {'title': _('Service')}},
            {'pool': {'title': _('Pool')}},
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {'source_ip': {'title': _('Src Ip')}},
            {'source_host': {'title': _('Src Host')}},
        ]

    def getRowStyle(self, parent):
        return {'field': 'state', 'prefix': 'row-state-'}

    def deleteItem(self, parent, item):  # This is also used by CachedService, so we use "userServices" directly and is valid for both
        service = None
        try:
            service = UserService.objects.get(uuid=processUuid(item))
            if service.deployed_service.service.provider.id != parent.id:
                # Forged UUID service!!!
                raise Exception('Access denied')
        except Exception:
            logger.exception('deleteItem')
            self.invalidItemException()

        logger.debug('Deleting user service')
        if service.state in (State.USABLE, State.REMOVING):
            service.remove()
        elif service.state == State.PREPARING:
            service.cancel()
        elif service.state == State.REMOVABLE:
            self.invalidItemException(_('Item already being removed'))
        else:
            self.invalidItemException(_('Item is not removable'))

        return self.success()
