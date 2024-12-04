# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import collections.abc
import typing

from uds import models
from uds.core import environment, types
from uds.core.osmanagers.osmanager import OSManager
from uds.core.transports import Transport

from ..utils import helpers

# Counters so we can reinvoke the same method and generate new data
glob = {
    'provider_id': 1,
    'service_id': 1,
    'osmanager_id': 1,
    'transport_id': 1,
    'service_pool_id': 1,
    'user_service_id': 1,
    'meta_pool_id': 1,
    'service_pool_group_id': 1,
}


def create_db_provider() -> models.Provider:
    from uds.services.Test.provider import TestProvider

    provider = models.Provider()
    provider.name = 'Testing provider {}'.format(glob['provider_id'])
    provider.comments = 'Tesging provider comment {}'.format(glob['provider_id'])
    provider.data_type = TestProvider.type_type
    provider.data = provider.get_instance().serialize()
    provider.save()
    glob['provider_id'] += 1

    return provider


def create_db_service(provider: models.Provider, use_caching_version: bool = True) -> models.Service:
    from uds.services.Test.service import TestServiceCache, TestServiceNoCache

    service = provider.services.create(
        name='Service {}'.format(glob['service_id']),
        data_type=TestServiceCache.type_type,
        data=(
            TestServiceCache(
                environment.Environment(str(glob['service_id'])), provider.get_instance()
            ).serialize()
            if use_caching_version
            else TestServiceNoCache(
                environment.Environment(str(glob['service_id'])), provider.get_instance()
            ).serialize()
        ),
        token=helpers.random_string(16) + str(glob['service_id']),
    )
    glob['service_id'] += 1  # In case we generate a some more services elsewhere

    return service


def create_db_osmanager(
    osmanager: typing.Optional[OSManager] = None,
) -> models.OSManager:
    if osmanager is None:
        from uds.osmanagers.Test import TestOSManager

        osmanager = TestOSManager(
            environment.Environment.testing_environment(),
            {
                'on_logout': 'remove',
                'idle': 300,
            },
        )

    osmanager_db = models.OSManager.objects.create(
        name=f'OS Manager {glob["osmanager_id"]}',
        comments=f'Comment for OS Manager {glob["osmanager_id"]}',
        data_type=osmanager.type_type,
        data=osmanager.serialize(),
    )
    glob['osmanager_id'] += 1

    return osmanager_db


def create_db_servicepool_group(
    image: typing.Optional[models.Image] = None,
) -> models.ServicePoolGroup:
    service_pool_group: 'models.ServicePoolGroup' = models.ServicePoolGroup.objects.create(
        name='Service pool group %d' % (glob['service_pool_group_id']),
        comments=f'Comment for service pool group {glob["service_pool_group_id"]}',
        image=image,
    )
    glob['service_pool_group_id'] += 1

    return service_pool_group


def create_db_servicepool(
    service: models.Service,
    osmanager: typing.Optional[models.OSManager] = None,
    groups: typing.Optional[collections.abc.Iterable[models.Group]] = None,
    transports: typing.Optional[collections.abc.Iterable[models.Transport]] = None,
    servicePoolGroup: typing.Optional[models.ServicePoolGroup] = None,
) -> models.ServicePool:

    service_pool: 'models.ServicePool' = service.deployedServices.create(
        name='Service pool %d' % (glob['service_pool_id']),
        short_name='pool%d' % (glob['service_pool_id']),
        comments='Comment for service pool %d' % (glob['service_pool_id']),
        osmanager=osmanager,
    )
    glob['service_pool_id'] += 1

    for g in groups or []:
        service_pool.assignedGroups.add(g)

    for t in transports or []:
        service_pool.transports.add(t)

    if servicePoolGroup is not None:
        service_pool.servicesPoolGroup = servicePoolGroup

    return service_pool


def create_db_publication(
    service_pool: models.ServicePool,
) -> models.ServicePoolPublication:
    publication: 'models.ServicePoolPublication' = service_pool.publications.create(
        publish_date=datetime.datetime.now(),
        state=types.states.State.USABLE,
        state_date=datetime.datetime.now(),
        # Rest of fields are left as default
    )
    service_pool.publications.add(publication)

    return publication


def create_db_transport(transport_instance: 'Transport|None' = None, **kwargs: typing.Any) -> models.Transport:
    from uds.transports.Test import TestTransport

    if transport_instance is None:
        transport_instance = TestTransport(environment.Environment.testing_environment(), None)

    transport: 'models.Transport' = models.Transport.objects.create(
        name='Transport %d' % (glob['transport_id']),
        comments='Comment for Transport %d' % (glob['transport_id']),
        data_type=transport_instance.type_type,
        data=transport_instance.serialize(),
        **kwargs,
    )
    glob['transport_id'] += 1
    return transport


def create_db_userservice(
    service_pool: models.ServicePool,
    publication: models.ServicePoolPublication,
    user: 'models.User|None',
) -> models.UserService:
    user_service: 'models.UserService' = service_pool.userServices.create(
        friendly_name='user-service-{}'.format(glob['user_service_id']),
        publication=publication,
        unique_id=helpers.random_mac(),
        state=types.states.State.USABLE,
        os_state=types.states.State.USABLE,
        state_date=datetime.datetime.now(),
        creation_date=datetime.datetime.now() - datetime.timedelta(minutes=30),
        user=user,
        src_hostname=helpers.random_string(32),
        src_ip=helpers.random_ip(),
    )
    glob['user_service_id'] += 1
    return user_service


def create_db_metapool(
    service_pools: collections.abc.Iterable[models.ServicePool],
    groups: collections.abc.Iterable[models.Group],
    round_policy: int = types.pools.LoadBalancingPolicy.ROUND_ROBIN,
    transport_grouping: int = types.pools.TransportSelectionPolicy.AUTO,
    ha_policy: int = types.pools.HighAvailabilityPolicy.ENABLED,
) -> models.MetaPool:
    meta_pool: 'models.MetaPool' = models.MetaPool.objects.create(
        name='Meta pool %d' % (glob['meta_pool_id']),
        short_name='meta%d' % (glob['meta_pool_id']),
        comments='Comment for meta pool %d' % (glob['meta_pool_id']),
        policy=round_policy,
        transport_grouping=transport_grouping,
        ha_policy=ha_policy,
    )
    glob['meta_pool_id'] += 1

    for g in groups:
        meta_pool.assignedGroups.add(g)

    for priority, pool in enumerate(service_pools):
        meta_pool.members.create(pool=pool, priority=priority, enabled=True)

    return meta_pool


def create_db_one_assigned_userservice(
    provider: 'models.Provider',
    user: 'models.User',
    groups: collections.abc.Iterable['models.Group'],
    type_: typing.Union[typing.Literal['managed'], typing.Literal['unmanaged']],
    osmanager: typing.Optional[OSManager] = None,
    transport_instance: typing.Optional['Transport'] = None,
) -> 'models.UserService':

    service = create_db_service(provider)

    """
    Creates several testing OS Managers
    """

    osmanager_db: typing.Optional['models.OSManager'] = (
        None if type_ == 'unmanaged' else create_db_osmanager(osmanager=osmanager)
    )
    transport: 'models.Transport' = create_db_transport(transport_instance=transport_instance)
    service_pool: 'models.ServicePool' = create_db_servicepool(service, osmanager_db, groups, [transport])
    publication: 'models.ServicePoolPublication' = create_db_publication(service_pool)

    return create_db_userservice(service_pool, publication, user)


def create_db_assigned_userservices(
    count: int = 1,
    type_: typing.Literal['managed', 'unmanaged'] = 'managed',
    user: typing.Optional['models.User'] = None,
    groups: typing.Optional[collections.abc.Iterable['models.Group']] = None,
    transport_instance: typing.Optional['Transport'] = None,
) -> list[models.UserService]:
    from . import authenticators

    if not user or not groups:
        auth = authenticators.create_db_authenticator()
        groups = authenticators.create_db_groups(auth, 3)
        user = authenticators.create_db_users(auth, 1, groups=groups)[0]
    user_services: list[models.UserService] = []
    for _ in range(count):
        user_services.append(
            create_db_one_assigned_userservice(
                create_db_provider(), user, groups, type_, transport_instance=transport_instance
            )
        )
    return user_services


def create_db_metapools_for_tests(
    user: models.User,
    groups: collections.abc.Iterable[models.Group],
    grouping_method: types.pools.TransportSelectionPolicy,
    ha_policy: types.pools.HighAvailabilityPolicy = types.pools.HighAvailabilityPolicy.DISABLED,
) -> None:
    # Create 10 services, for this user
    service_pools: list[models.ServicePool] = [
        create_db_assigned_userservices(count=1, user=user, groups=groups)[
            0
        ].service_pool  # We only need the service pool
        for _i in range(110)
    ]

    # Create 10 meta services, for this user, last 10 user_services will not be added to meta pools
    _meta_services: list[models.MetaPool] = [
        create_db_metapool(
            service_pools=service_pools[i * 10 : (i + 1) * 10],
            groups=groups,
            transport_grouping=grouping_method,
            ha_policy=ha_policy,
        )
        for i in range(10)
    ]
