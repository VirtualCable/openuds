# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2023 Virtual Cable S.L.U.
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
import logging
import operator
import typing
import collections.abc

from django.db import models
from django.db.models import QuerySet, signals
from django.utils.translation import gettext_noop as _

from uds.core import consts, types
from uds.core.util import log, states
from uds.core.util.calendar import CalendarChecker

from ..core.util.model import sql_datetime
from .group import Group
from .image import Image
from .service_pool import ServicePool
from .service_pool_group import ServicePoolGroup
from .tag import TaggingMixin
from .uuid_model import UUIDModel

if typing.TYPE_CHECKING:
    import datetime

    from uds.models import CalendarAccessMeta, User


logger = logging.getLogger(__name__)


class MetaPool(UUIDModel, TaggingMixin):  # type: ignore
    """
    A meta pool is a pool that has pool members
    """

    name = models.CharField(max_length=192, default='')  # Give enouth space for "macros"
    short_name = models.CharField(max_length=96, default='')  # Give enouth space for "macros"
    comments = models.CharField(max_length=256, default='')
    visible = models.BooleanField(default=True)
    image = models.ForeignKey(
        Image,
        null=True,
        blank=True,
        related_name='metaPools',
        on_delete=models.SET_NULL,
    )
    servicesPoolGroup = models.ForeignKey(
        ServicePoolGroup,
        null=True,
        blank=True,
        related_name='metaPools',
        on_delete=models.SET_NULL,
    )
    assignedGroups = models.ManyToManyField(Group, related_name='metaPools', db_table='uds__meta_grps')

    # Message if access denied
    calendar_message = models.CharField(default='', max_length=256)
    # Default fallback action for access
    fallbackAccess = models.CharField(default=states.action.ALLOW, max_length=8)

    # Pool selection policy
    policy = models.SmallIntegerField(default=types.pools.LoadBalancingPolicy.ROUND_ROBIN)
    # If use common transports instead of auto select one
    transport_grouping = models.IntegerField(default=types.pools.TransportSelectionPolicy.AUTO)
    # HA policy
    ha_policy = models.SmallIntegerField(default=types.pools.HighAvailabilityPolicy.DISABLED)

    # "fake" declarations for type checking
    # objects: 'models.BaseManager["MetaPool"]'
    calendarAccess: 'models.manager.RelatedManager[CalendarAccessMeta]'
    members: 'models.manager.RelatedManager["MetaPoolMember"]'

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__pool_meta'
        app_label = 'uds'

    @property
    def allow_users_remove(self) -> bool:
        # Returns true if all members allow users remove
        for p in self.members.all():
            if not p.pool.allow_users_remove:
                return False
        return True

    @property
    def allow_users_reset(self) -> bool:
        # Returns true if all members allow users reset
        for p in self.members.all():
            if not p.pool.allow_users_reset:
                return False
        return True

    def is_in_maintenance(self) -> bool:
        """If a Metapool is in maintenance (that is, all its pools are in maintenance)

        Returns:
            bool -- [description]
        """
        total, maintenance = 0, 0
        p: 'MetaPoolMember'
        for p in self.members.all():
            total += 1
            if p.pool.is_in_maintenance():
                maintenance += 1
        return total == maintenance

    def is_access_allowed(self, chkDateTime: typing.Optional['datetime.datetime'] = None) -> bool:
        """
        Checks if the access for a service pool is allowed or not (based esclusively on associated calendars)
        """
        if chkDateTime is None:
            chkDateTime = sql_datetime()

        access = self.fallbackAccess
        # Let's see if we can access by current datetime
        for ac in sorted(self.calendarAccess.all(), key=operator.attrgetter('priority')):
            if CalendarChecker(ac.calendar).check(chkDateTime):
                access = ac.access
                break  # Stops on first rule match found

        return access == states.action.ALLOW

    def usage(self, cachedValue=-1) -> types.pools.UsageInfo:
        """
        Returns the % used services, then count and the max related to "maximum" user services
        If no "maximum" number of services, will return 0% ofc
        cachedValue is used to optimize (if known the number of assigned services, we can avoid to query the db)
        Note:
            No metapoools, cachedValue is ignored, but keep for consistency with servicePool
        """
        # If no pools, return 0%
        if self.members.count() == 0:
            return types.pools.UsageInfo(0, 0)

        query = (
            ServicePool.objects.filter(
                memberOfMeta__meta_pool=self,
                state=states.servicePool.ACTIVE,
            )
            .annotate(
                usage_count=models.Count(
                    'userServices',
                    filter=models.Q(
                        userServices__state__in=states.userService.VALID_STATES,
                        userServices__cache_level=0,
                    ),
                    distinct=True,
                )
            )
            .prefetch_related(
                'service',
                'service__provider',
            )
        )

        usage_count = 0
        max_count = 0
        for pool in query:
            poolInfo = pool.usage(pool.usage_count)  # type:ignore  # Anotated field
            usage_count += poolInfo.used
            # If any of the pools has no max, then max is -1
            if max_count == consts.UNLIMITED or poolInfo.total == consts.UNLIMITED:
                max_count = consts.UNLIMITED
            else:
                max_count += poolInfo.total

        if max_count == 0 or max_count == consts.UNLIMITED:
            return types.pools.UsageInfo(usage_count, consts.UNLIMITED)

        return types.pools.UsageInfo(usage_count, max_count)

    @property
    def visual_name(self) -> str:
        logger.debug('SHORT: %s %s %s', self.short_name, self.short_name is not None, self.name)
        sn = str(self.short_name).strip()
        return sn if sn else self.name

    @staticmethod
    def metapools_for_groups(
        groups: collections.abc.Iterable['Group'], user: typing.Optional['User'] = None
    ) -> 'QuerySet[MetaPool]':
        """
        Return deployed services with publications for the groups requested.

        Args:
            groups: List of groups to check

        Returns:
            List of accesible deployed services
        """
        # Get services that HAS publications
        meta = MetaPool.objects.filter(
            assignedGroups__in=groups,
            assignedGroups__state=states.group.ACTIVE,
            visible=True,
        ).prefetch_related(
            'servicesPoolGroup',
            'servicesPoolGroup__image',
            'assignedGroups',
            'assignedGroups',
            'members__pool',
            'members__pool__service',
            'members__pool__service__provider',
            'members__pool__image',
            'members__pool__transports',
            'members__pool__transports__networks',
            'calendarAccess',
            'calendarAccess__calendar',
            'calendarAccess__calendar__rules',
            'image',
        )
        if user:
            meta = meta.annotate(
                number_in_use=models.Count(
                    'members__pool__userServices',
                    filter=models.Q(
                        members__pool__userServices__user=user,
                        members__pool__userServices__in_use=True,
                        members__pool__userServices__state__in=states.userService.USABLE,
                    ),
                )
            )

        # May we can include some other filters?
        return meta

    @staticmethod
    def pre_delete(sender, **kwargs) -> None:
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean  # pylint: disable=import-outside-toplevel

        toDelete: 'MetaPool' = kwargs['instance']

        # Clears related logs
        log.clear_logs(toDelete)

        # Clears related permissions
        clean(toDelete)

    def __str__(self):
        return f'Meta pool: {self.name}, no. pools: {self.members.all().count()}, visible: {self.visible}, policy: {self.policy}'


# Connects a pre deletion signal
signals.pre_delete.connect(MetaPool.pre_delete, sender=MetaPool)


class MetaPoolMember(UUIDModel):
    pool = models.ForeignKey(ServicePool, related_name='memberOfMeta', on_delete=models.CASCADE)
    meta_pool = models.ForeignKey(MetaPool, related_name='members', on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__meta_pool_member'
        app_label = 'uds'

    def __str__(self) -> str:
        return f'Meta pool member: {self.pool.name}/{self.meta_pool.name}, priority: {self.priority}, enabled: {self.enabled}'
