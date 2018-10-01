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

from uds.models.MetaPool import MetaPool, MetaPoolMember
from uds.models.ServicesPool import ServicePool

from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.REST.model import DetailHandler
import logging

logger = logging.getLogger(__name__)

ALLOW = 'ALLOW'
DENY = 'DENY'


class MetaServicesPool(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    @staticmethod
    def as_dict(item: MetaPoolMember):
        return {
            'id': item.uuid,
            'name': item.pool.name,
            'comments': item.pool.comments,
            'priority': item.priority,
            'enabled': item.enabled,
            'user_services_count': item.pool.userServices.exclude(state__in=State.INFO_STATES).count(),
            'user_services_in_preparation': item.pool.userServices.filter(state=State.PREPARING).count(),
            'priority': item.priority,
        }

    def getItems(self, parent: MetaPool, item: str):
        try:
            if item is None:
                return [MetaServicesPool.as_dict(i) for i in parent.members.all()]
            else:
                i = parent.members.get(uuid=processUuid(item))
                return MetaServicesPool.as_dict(i)
        except Exception:
            logger.exception('err: %s', item)
            self.invalidItemException()

    def getTitle(self, parent):
        return _('Service pools')

    def getFields(self, parent):
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'name': {'title': _('Service Pool name')}},
            {'enabled': {'title': _('Enabled')}},
        ]

    def saveItem(self, parent: MetaPool, item):
        # If already exists
        uuid = processUuid(item) if item is not None else None

        pool = ServicePool.objects.get(uuid=processUuid(self._params['servicePoolId']))
        enabled = self._params['enabled'].upper() in ('1', 'TRUE')
        priority = int(self._params['priority'])

        if uuid is not None:
            member = parent.members.get(uuid=uuid)
            member.pool = pool
            member.enabled = enabled
            member.priority = priority
            member.save()
        else:
            parent.members.create(pool=pool, priority=priority, enabled=enabled)

        log.doLog(parent, log.INFO, "Added meta pool member {}/{} by {}".format(pool.name, priority, self._user.pretty_name), log.ADMIN)

        return self.success()

    def deleteItem(self, parent: MetaPool, item: str):
        member = parent.members.get(uuid=processUuid(self._args[0]))
        logStr = "Removed meta pool member {} by {}".format(member.pool.name, self._user.pretty_name)

        member.delete()

        log.doLog(parent, log.INFO, logStr, log.ADMIN)

        return self.success()
