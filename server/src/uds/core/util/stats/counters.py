# -*- coding: utf-8 -*-
#
# Copyright (c) 2013-2023 Virtual Cable S.L.U.
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
import enum
import datetime
import logging
import typing
import collections.abc

from django.utils.translation import gettext_lazy as _
from django.db.models import Model

from uds.core.managers.stats import StatsManager, AccumStat
from uds.models import (
    Provider,
    Service,
    ServicePool,
    Authenticator,
    StatsCountersAccum,
)
from uds.core import consts, types


logger = logging.getLogger(__name__)

CounterClass = typing.TypeVar('CounterClass', Provider, Service, ServicePool, Authenticator)


# Helpers
def _get_id(obj: 'CounterClass') -> typing.Optional[int]:
    return obj.id if obj.id != -1 else None


def _get_prov_serv_ids(provider: 'Provider') -> tuple[int, ...]:
    return tuple(i.id for i in provider.services.all())


def _get_serv_pool_ids(service: 'Service') -> tuple[int, ...]:
    return tuple(i.id for i in service.deployedServices.all())


def _get_prov_serv_pool_ids(provider: 'Provider') -> tuple[int, ...]:
    res: tuple[int, ...] = ()
    for i in provider.services.all():
        res += _get_serv_pool_ids(i)
    return res


_id_retriever: typing.Final[
    collections.abc.Mapping[type[Model], collections.abc.Mapping[int, collections.abc.Callable[[typing.Any], typing.Any]]]
] = {
    Provider: {
        types.stats.CounterType.LOAD: _get_id,
        types.stats.CounterType.STORAGE: _get_prov_serv_ids,
        types.stats.CounterType.ASSIGNED: _get_prov_serv_pool_ids,
        types.stats.CounterType.INUSE: _get_prov_serv_pool_ids,
    },
    Service: {
        types.stats.CounterType.STORAGE: _get_id,
        types.stats.CounterType.ASSIGNED: _get_serv_pool_ids,
        types.stats.CounterType.INUSE: _get_serv_pool_ids,
    },
    ServicePool: {
        types.stats.CounterType.ASSIGNED: _get_id,
        types.stats.CounterType.INUSE: _get_id,
        types.stats.CounterType.CACHED: _get_id,
    },
    Authenticator: {
        types.stats.CounterType.AUTH_USERS: _get_id,
        types.stats.CounterType.AUTH_SERVICES: _get_id,
        types.stats.CounterType.AUTH_USERS_WITH_SERVICES: _get_id,
    },
}

_valid_model_for_counterype: typing.Final[collections.abc.Mapping[int, tuple[type[Model], ...]]] = {
    types.stats.CounterType.LOAD: (Provider,),
    types.stats.CounterType.STORAGE: (Service,),
    types.stats.CounterType.ASSIGNED: (ServicePool,),
    types.stats.CounterType.INUSE: (ServicePool,),
    types.stats.CounterType.AUTH_USERS: (Authenticator,),
    types.stats.CounterType.AUTH_SERVICES: (Authenticator,),
    types.stats.CounterType.AUTH_USERS_WITH_SERVICES: (Authenticator,),
    types.stats.CounterType.CACHED: (ServicePool,),
}

_obj_type_from_model: typing.Final[collections.abc.Mapping[type[Model], types.stats.CounterOwnerType]] = {
    ServicePool: types.stats.CounterOwnerType.SERVICEPOOL,
    Service: types.stats.CounterOwnerType.SERVICE,
    Provider: types.stats.CounterOwnerType.PROVIDER,
    Authenticator: types.stats.CounterOwnerType.AUTHENTICATOR,
}


def add_counter(
    obj: CounterClass,
    counterType: types.stats.CounterType,
    counterValue: int,
    stamp: typing.Optional[datetime.datetime] = None,
) -> bool:
    """
    Adds a counter stat to specified object

    Although any counter type can be added to any object, there is a relation that must be observed
    or, otherway, the stats will not be recoverable at all:


    note: Runtime checks are done so if we try to insert an unssuported stat, this won't be inserted and it will be logged
    """
    type_ = type(obj)
    if type_ not in _valid_model_for_counterype.get(counterType, ()):  # pylint: disable
        logger.error(
            'Type %s does not accepts counter of type %s',
            type_,
            counterValue,
            exc_info=True,
        )
        return False

    return StatsManager.manager().add_counter(
        _obj_type_from_model[type(obj)], obj.id, counterType, counterValue, stamp
    )


def enumerate_counters(
    obj: CounterClass, counterType: types.stats.CounterType, **kwargs: typing.Any
) -> typing.Generator[tuple[datetime.datetime, int], None, None]:
    """
    Get counters

    Args:
        obj: Obj for which to recover stats counters
        counterType: type of counter to recover
        since: (optional, defaults to 'Since beginning') Start date for counters to recover
        to: (optional, defaults to 'Until end') En date for counter to recover
        limit: (optional, defaults to 1000) Number of counter to recover. This is an 'At most' advice. The returned number of value
               can be lower, or even 1 more than requested due to a division for retrieving object at database

    Returns:
        A generator, that contains pairs of (stamp, value) tuples
    """
    since = kwargs.get('since') or consts.NEVER
    to = kwargs.get('to') or datetime.datetime.now()
    limit = kwargs.get('limit')
    use_max = kwargs.get('use_max', False)
    type_ = type(obj)

    readFncTbl = _id_retriever.get(type_)

    if not readFncTbl:
        logger.error('Type %s has no registered stats', type_)
        return

    fnc = readFncTbl.get(counterType)

    if not fnc:
        logger.error('Type %s has no registerd stats of type %s', type_, counterType)
        return

    if not kwargs.get('all', False):
        owner_ids = fnc(obj)  # pyright: ignore
    else:
        owner_ids = None

    for i in StatsManager.manager().enumerate_counters(
        _obj_type_from_model[type(obj)],
        counterType,
        owner_ids,
        since,
        to,
        kwargs.get('interval'),
        kwargs.get('max_intervals'),
        limit,
        use_max,
    ):
        yield (datetime.datetime.fromtimestamp(i[0]), i[1])


def get_accumulated_counters(
    intervalType: StatsCountersAccum.IntervalType,
    counterType: types.stats.CounterType,
    onwer_type: typing.Optional[types.stats.CounterOwnerType] = None,
    owner_id: typing.Optional[int] = None,
    since: typing.Optional[typing.Union[datetime.datetime, int]] = None,
    points: typing.Optional[int] = None,
) -> typing.Generator[AccumStat, None, None]:
    yield from StatsManager.manager().get_accumulated_counters(
        intervalType=intervalType,
        counterType=counterType,
        owner_type=onwer_type,
        owner_id=owner_id,
        since=since,
        points=points,
    )
