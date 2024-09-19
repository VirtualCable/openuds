# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
import datetime
import logging
import typing
import collections.abc

from django.db import models

from uds.core import types

logger = logging.getLogger(__name__)


class StatsEvents(models.Model):
    """
    Statistics about events (login, logout, whatever...)
    """

    owner_id = models.IntegerField(db_index=True, default=0)
    owner_type = models.SmallIntegerField(db_index=True, default=0)
    event_type = models.SmallIntegerField(db_index=True, default=0)
    stamp = models.IntegerField(db_index=True, default=0)

    # Variable fields, depends on event
    fld1 = models.CharField(max_length=128, default='')
    fld2 = models.CharField(max_length=128, default='')
    fld3 = models.CharField(max_length=128, default='')
    fld4 = models.CharField(max_length=128, default='')

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager[StatsEvents]'

    class Meta:  # pyright: ignore
        """
        Meta class to declare db table
        """

        db_table = 'uds_stats_e'
        app_label = 'uds'

    @staticmethod
    def enumerate_stats(
        owner_type: typing.Union[
            types.stats.EventOwnerType, collections.abc.Iterable[types.stats.EventOwnerType]
        ],
        event_type: typing.Union[types.stats.EventType, collections.abc.Iterable[types.stats.EventType]],
        **kwargs: typing.Any,
    ) -> 'models.QuerySet[StatsEvents]':
        """
        Returns a queryset with the average stats grouped by interval for owner_type and owner_id (optional)
        """
        q = StatsEvents.objects.filter()
        if isinstance(owner_type, int):
            q = q.filter(owner_type=owner_type)
        else:
            q = q.filter(owner_type__in=owner_type)
        if isinstance(event_type, int):
            q = q.filter(event_type=event_type)
        else:
            q = q.filter(event_type__in=event_type)

        if 'owner_id' in kwargs:
            owner_id = kwargs['owner_id']
            if isinstance(owner_id, int):
                q = q.filter(owner_id=owner_id)
            else:
                q = q.filter(owner_id__in=owner_id)

        since = kwargs.get('since')
        if isinstance(since, datetime.datetime):
            # Convert to unix timestamp
            since = int(since.timestamp())
        if since and isinstance(since, int):
            q = q.filter(stamp__gte=since)
        to = kwargs.get('to')
        if isinstance(to, datetime.datetime):
            # Convert to unix timestamp
            to = int(to.timestamp())
        if to and isinstance(to, int):
            q = q.filter(stamp__lte=to)

        if kwargs.get('limit') and isinstance(kwargs['limit'], int) and kwargs['limit'] > 0:
            q = q[: kwargs['limit']]

        return q

    # Utility aliases for reading
    @property
    def username(self) -> str:
        return self.fld1

    @property
    def src_ip(self) -> str:
        # If ipv6, return full, if not, split it by ':' and return first part
        if '[' in self.fld2:
            return self.fld2
        return self.fld2.split(':')[0]

    @property
    def dst_ip(self) -> str:
        return self.fld3

    @property
    def unique_id(self) -> str:
        return self.fld4
    
    # on userservice events, fld4 is full username
    @property
    def full_username(self) -> str:
        return self.fld4

    @property
    def isostamp(self) -> str:
        """
        Returns the timestamp in ISO format (UTC)
        """
        stamp = datetime.datetime.fromtimestamp(self.stamp, datetime.UTC)
        return stamp.isoformat()

    # returns CSV header
    @staticmethod
    def get_csv_header(
        sep: str = '',
    ) -> str:
        return sep.join(
            [
                'owner_type',
                'owner_id',
                'event_type',
                'stamp',
                'field_1',
                'field_2',
                'field_3',
                'field_4',
            ]
        )

    # Return record as csv line using separator (default: ',')
    def as_csv(self, sep: str = ',') -> str:

        return sep.join(
            [
                types.stats.EventOwnerType.from_int(self.owner_type).owner_name,
                str(self.owner_id),
                types.stats.EventType.from_int(self.event_type).event_name,
                str(self.isostamp),
                self.fld1,
                self.fld2,
                self.fld3,
                self.fld4,
            ]
        )

    def __str__(self) -> str:
        return (
            f'Log of {self.owner_type}({self.owner_id}): {self.event_type} - {self.stamp}, '
            f'{self.fld1}, {self.fld2}, {self.fld3}'
        )
