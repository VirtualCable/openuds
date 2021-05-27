# -*- coding: utf-8 -*-

#
# Copyright (c) 2018-2020 Virtual Cable S.L.U.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models
from django.db.models import signals, QuerySet
from django.utils.translation import ugettext_noop as _

from uds.core.util import log
from uds.core.util import states
from uds.core.util.calendar import CalendarChecker

from .uuid_model import UUIDModel
from .tag import TaggingMixin
from .util import getSqlDatetime

from .image import Image
from .service_pool_group import ServicePoolGroup
from .service_pool import ServicePool
from .group import Group

if typing.TYPE_CHECKING:
    import datetime
    from uds.models import User, CalendarAccessMeta


logger = logging.getLogger(__name__)


class MetaPool(UUIDModel, TaggingMixin):  # type: ignore
    """
    A meta pool is a pool that has pool members
    """

    # Type of pool selection for meta pool
    ROUND_ROBIN_POOL = 0
    PRIORITY_POOL = 1
    MOST_AVAILABLE_BY_NUMBER = 2

    TYPES: typing.Mapping[int, str] = {
        ROUND_ROBIN_POOL: _('Evenly distributed'),
        PRIORITY_POOL: _('Priority'),
        MOST_AVAILABLE_BY_NUMBER: _('Greater % available'),
    }

    # Type of transport grouping
    AUTO_TRANSPORT_SELECT = 0
    COMMON_TRANSPORT_SELECT = 1
    LABEL_TRANSPORT_SELECT = 2
    TRANSPORT_SELECT: typing.Mapping[int, str] = {
        AUTO_TRANSPORT_SELECT: _('Automatic selection'),
        COMMON_TRANSPORT_SELECT: _('Use only common transports'),
        LABEL_TRANSPORT_SELECT: _('Group Transports by label')
    }

    name = models.CharField(max_length=128, default='')
    short_name = models.CharField(max_length=32, default='')
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
    assignedGroups = models.ManyToManyField(
        Group, related_name='metaPools', db_table='uds__meta_grps'
    )

    # Message if access denied
    calendar_message = models.CharField(default='', max_length=256)
    # Default fallback action for access
    fallbackAccess = models.CharField(default=states.action.ALLOW, max_length=8)

    # Pool selection policy
    policy = models.SmallIntegerField(default=0)
    # If use common transports instead of auto select one
    transport_grouping = models.IntegerField(default=0)

    # "fake" declarations for type checking
    objects: 'models.BaseManager[MetaPool]'
    calendarAccess: 'models.QuerySet[CalendarAccessMeta]'
    members: 'models.QuerySet[MetaPoolMember]'

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__pool_meta'
        app_label = 'uds'

    def isInMaintenance(self) -> bool:
        """If a Metapool is in maintenance (that is, all its pools are in maintenance)

        Returns:
            bool -- [description]
        """
        total, maintenance = 0, 0
        p: 'MetaPoolMember'
        for p in self.members.all():
            total += 1
            if p.pool.isInMaintenance():
                maintenance += 1
        return total == maintenance

    def isAccessAllowed(
        self, chkDateTime: typing.Optional['datetime.datetime'] = None
    ) -> bool:
        """
        Checks if the access for a service pool is allowed or not (based esclusively on associated calendars)
        """
        if chkDateTime is None:
            chkDateTime = getSqlDatetime()

        access = self.fallbackAccess
        # Let's see if we can access by current datetime
        for ac in sorted(self.calendarAccess.all(), key=lambda x: x.priority):
            if CalendarChecker(ac.calendar).check(chkDateTime):
                access = ac.access
                break  # Stops on first rule match found

        return access == states.action.ALLOW

    @property
    def visual_name(self) -> str:
        logger.debug(
            'SHORT: %s %s %s', self.short_name, self.short_name is not None, self.name
        )
        if self.short_name.strip():
            return self.short_name
        return self.name

    @staticmethod
    def getForGroups(
        groups: typing.Iterable['Group'], user: typing.Optional['User'] = None
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
        # TODO: Maybe we can exclude non "usable" metapools (all his pools are in maintenance mode?)

        return meta

    @staticmethod
    def beforeDelete(sender, **kwargs):
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        from uds.core.util.permissions import clean

        toDelete = kwargs['instance']

        # Clears related logs
        log.clearLogs(toDelete)

        # Clears related permissions
        clean(toDelete)

    def __str__(self):
        return 'Meta pool: {}, no. pools: {}, visible: {}, policy: {}'.format(
            self.name, self.members.all().count(), self.visible, self.policy
        )


# Connects a pre deletion signal
signals.pre_delete.connect(MetaPool.beforeDelete, sender=MetaPool)


class MetaPoolMember(UUIDModel):
    pool: 'models.ForeignKey[MetaPoolMember, ServicePool]' = models.ForeignKey(
        ServicePool, related_name='memberOfMeta', on_delete=models.CASCADE
    )
    meta_pool: 'models.ForeignKey[MetaPoolMember, MetaPool]' = models.ForeignKey(
        MetaPool, related_name='members', on_delete=models.CASCADE
    )
    priority = models.PositiveIntegerField(default=0)
    enabled = models.BooleanField(default=True)

    class Meta(UUIDModel.Meta):
        """
        Meta class to declare the name of the table at database
        """

        db_table = 'uds__meta_pool_member'
        app_label = 'uds'

    def __str__(self) -> str:
        return '{}/{} {} {}'.format(
            self.pool.name, self.meta_pool.name, self.priority, self.enabled
        )
