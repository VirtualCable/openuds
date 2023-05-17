# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
import typing

from django.utils.translation import gettext as _

from uds.models.meta_pool import MetaPool, MetaPoolMember
from uds.models.service_pool import ServicePool
from uds.models.user_service import UserService
from uds.models.user import User

from uds.core.util.state import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.REST.model import DetailHandler
from .user_services import AssignedService

logger = logging.getLogger(__name__)


class MetaServicesPool(DetailHandler):
    """
    Processes the transports detail requests of a Service Pool
    """

    @staticmethod
    def as_dict(item: MetaPoolMember):
        return {
            'id': item.uuid,
            'pool_id': item.pool.uuid,
            'name': item.pool.name,
            'comments': item.pool.comments,
            'priority': item.priority,
            'enabled': item.enabled,
            'user_services_count': item.pool.userServices.exclude(
                state__in=State.INFO_STATES
            ).count(),
            'user_services_in_preparation': item.pool.userServices.filter(
                state=State.PREPARING
            ).count(),
        }

    def getItems(self, parent: MetaPool, item: typing.Optional[str]):
        try:
            if not item:
                return [MetaServicesPool.as_dict(i) for i in parent.members.all()]
            i = parent.members.get(uuid=processUuid(item))
            return MetaServicesPool.as_dict(i)
        except Exception:
            logger.exception('err: %s', item)
            raise self.invalidItemException()

    def getTitle(self, parent: MetaPool) -> str:
        return _('Service pools')

    def getFields(self, parent: MetaPool) -> typing.List[typing.Any]:
        return [
            {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
            {'name': {'title': _('Service Pool name')}},
            {'enabled': {'title': _('Enabled')}},
        ]

    def saveItem(self, parent: MetaPool, item: typing.Optional[str]):
        # If already exists
        uuid = processUuid(item) if item else None

        pool = ServicePool.objects.get(uuid=processUuid(self._params['pool_id']))
        enabled = self._params['enabled'] not in ('false', False, '0', 0)
        priority = int(self._params['priority'])
        priority = priority if priority >= 0 else 0

        if uuid is not None:
            member = parent.members.get(uuid=uuid)
            member.pool = pool  # type: ignore
            member.enabled = enabled
            member.priority = priority
            member.save()
        else:
            parent.members.create(pool=pool, priority=priority, enabled=enabled)

        log.doLog(
            parent,
            log.LogLevel.INFO,
            ("Added" if uuid is None else "Modified")
            + " meta pool member {}/{}/{} by {}".format(
                pool.name, priority, enabled, self._user.pretty_name
            ),
            log.LogSource.ADMIN,
        )

        return self.success()

    def deleteItem(self, parent: MetaPool, item: str):
        member = parent.members.get(uuid=processUuid(self._args[0]))
        logStr = "Removed meta pool member {} by {}".format(
            member.pool.name, self._user.pretty_name
        )

        member.delete()

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)


class MetaAssignedService(DetailHandler):
    """
    Rest handler for Assigned Services, wich parent is Service
    """

    @staticmethod
    def itemToDict(metaPool, item):
        element = AssignedService.itemToDict(item, False)
        element['pool_id'] = item.deployed_service.uuid
        element['pool_name'] = item.deployed_service.name
        return element

    def _getAssignedService(
        self, metaPool: MetaPool, userServiceId: str
    ) -> UserService:
        """
        Gets an assigned service and checks that it belongs to this metapool
        If not found, raises InvalidItemException
        """
        try:
            return UserService.objects.filter(
                uuid=processUuid(userServiceId),
                cache_level=0,
                deployed_service__in=[i.pool for i in metaPool.members.all()],
            )[0]
        except Exception:
            raise self.invalidItemException()

    def getItems(self, parent: MetaPool, item: typing.Optional[str]):
        def assignedUserServicesForPools():
            for m in parent.members.filter(enabled=True):
                for u in (
                    m.pool.assignedUserServices()
                    .filter(state__in=State.VALID_STATES)
                    .prefetch_related('properties')
                    .prefetch_related('deployed_service')
                    .prefetch_related('publication')
                ):
                    yield u

        try:
            if not item:  # All items
                result = {}
                for k in assignedUserServicesForPools():
                    result[k.uuid] = MetaAssignedService.itemToDict(parent, k)
                return list(result.values())

            return MetaAssignedService.itemToDict(
                parent, self._getAssignedService(parent, item)
            )
        except Exception:
            logger.exception('getItems')
            raise self.invalidItemException()

    def getTitle(self, parent: MetaPool) -> str:
        return _('Assigned services')

    def getFields(self, parent: MetaPool) -> typing.List[typing.Any]:
        return [
            {'creation_date': {'title': _('Creation date'), 'type': 'datetime'}},
            {'pool_name': {'title': _('Pool')}},
            {'unique_id': {'title': 'Unique ID'}},
            {'ip': {'title': _('IP')}},
            {'friendly_name': {'title': _('Friendly name')}},
            {
                'state': {
                    'title': _('status'),
                    'type': 'dict',
                    'dict': State.dictionary(),
                }
            },
            {'in_use': {'title': _('In Use')}},
            {'source_host': {'title': _('Src Host')}},
            {'source_ip': {'title': _('Src Ip')}},
            {'owner': {'title': _('Owner')}},
            {'actor_version': {'title': _('Actor version')}},
        ]

    def getRowStyle(self, parent: MetaPool) -> typing.Dict[str, typing.Any]:
        return {'field': 'state', 'prefix': 'row-state-'}

    def getLogs(self, parent: MetaPool, item: str) -> typing.List[typing.Any]:
        try:
            asignedService = self._getAssignedService(parent, item)
            logger.debug('Getting logs for %s', asignedService)
            return log.getLogs(asignedService)
        except Exception:
            raise self.invalidItemException()

    def deleteItem(self, parent: MetaPool, item: str) -> None:
        userService = self._getAssignedService(parent, item)

        if userService.user:
            logStr = 'Deleted assigned service {} to user {} by {}'.format(
                userService.friendly_name,
                userService.user.pretty_name,
                self._user.pretty_name,
            )
        else:
            logStr = 'Deleted cached service {} by {}'.format(
                userService.friendly_name, self._user.pretty_name
            )

        if userService.state in (State.USABLE, State.REMOVING):
            userService.remove()
        elif userService.state == State.PREPARING:
            userService.cancel()
        elif userService.state == State.REMOVABLE:
            raise self.invalidItemException(_('Item already being removed'))
        else:
            raise self.invalidItemException(_('Item is not removable'))

        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)

    # Only owner is allowed to change right now
    def saveItem(self, parent: MetaPool, item: typing.Optional[str]):
        if item is None:
            raise self.invalidItemException()

        fields = self.readFieldsFromParams(['auth_id', 'user_id'])
        service = self._getAssignedService(parent, item)
        user: User = User.objects.get(uuid=processUuid(fields['user_id']))

        logStr = 'Changing ownership of service from {} to {} by {}'.format(
            service.user.pretty_name if service.user else 'unknown', user.pretty_name, self._user.pretty_name
        )

        # If there is another service that has this same owner, raise an exception
        if (
            service.deployed_service.userServices.filter(user=user)
            .exclude(uuid=service.uuid)
            .exclude(state__in=State.INFO_STATES)
            .count()
            > 0
        ):
            raise self.invalidResponseException(
                'There is already another user service assigned to {}'.format(
                    user.pretty_name
                )
            )

        service.user = user  # type: ignore
        service.save()

        # Log change
        log.doLog(parent, log.LogLevel.INFO, logStr, log.LogSource.ADMIN)
