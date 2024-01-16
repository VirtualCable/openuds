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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import typing
import collections.abc

from uds import models
from uds.core import environment, types

from ..utils import generators

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


def createProvider() -> models.Provider:
    from uds.services.Test.provider import TestProvider

    provider = models.Provider()
    provider.name = 'Testing provider {}'.format(glob['provider_id'])
    provider.comments = 'Tesging provider comment {}'.format(glob['provider_id'])
    provider.data_type = TestProvider.type_type
    provider.data = provider.get_instance().serialize()
    provider.save()
    glob['provider_id'] += 1

    return provider


def createService(provider: models.Provider, useCachingVersion: bool = True) -> models.Service:
    from uds.services.Test.service import TestServiceCache, TestServiceNoCache

    service = provider.services.create(
        name='Service {}'.format(glob['service_id']),
        data_type=TestServiceCache.type_type,
        data=TestServiceCache(
            environment.Environment(str(glob['service_id'])), provider.get_instance()
        ).serialize()
        if useCachingVersion
        else TestServiceNoCache(
            environment.Environment(str(glob['service_id'])), provider.get_instance()
        ).serialize(),
        token=generators.random_string(16) + str(glob['service_id']),
    )
    glob['service_id'] += 1  # In case we generate a some more services elsewhere

    return service


def create_test_osmanager() -> models.OSManager:
    from uds.osmanagers.Test import TestOSManager

    values: dict[str, typing.Any] = {
        'on_logout': 'remove',
        'idle': 300,
    }
    osmanager = models.OSManager.objects.create(
        name='OS Manager %d' % (glob['osmanager_id']),
        comments='Comment for OS Manager %d' % (glob['osmanager_id']),
        data_type=TestOSManager.type_type,
        data=TestOSManager(environment.Environment(str(glob['osmanager_id'])), values).serialize(),
    )
    glob['osmanager_id'] += 1

    return osmanager


def createServicePoolGroup(
    image: typing.Optional[models.Image] = None,
) -> models.ServicePoolGroup:
    service_pool_group: 'models.ServicePoolGroup' = models.ServicePoolGroup.objects.create(
        name='Service pool group %d' % (glob['service_pool_group_id']),
        comments=f'Comment for service pool group {glob["service_pool_group_id"]}',
        image=image,
    )
    glob['service_pool_group_id'] += 1

    return service_pool_group


def create_test_servicepool(
    service: models.Service,
    osmanager: typing.Optional[models.OSManager] = None,
    groups: typing.Optional[list[models.Group]] = None,
    transports: typing.Optional[list[models.Transport]] = None,
    servicePoolGroup: typing.Optional[models.ServicePoolGroup] = None,
) -> models.ServicePool:
    from uds.services.Test.service import TestServiceCache, TestServiceNoCache
    from uds.osmanagers.Test import TestOSManager

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


def create_test_publication(
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


def create_test_transport() -> models.Transport:
    from uds.transports.Test import TestTransport

    values = TestTransport(
        environment.Environment.get_temporary_environment(), None
    ).get_dict_of_fields_values()
    transport: 'models.Transport' = models.Transport.objects.create(
        name='Transport %d' % (glob['transport_id']),
        comments='Comment for Transport %d' % (glob['transport_id']),
        data_type=TestTransport.type_type,
        data=TestTransport(environment.Environment(str(glob['transport_id'])), values).serialize(),
    )
    glob['transport_id'] += 1
    return transport


def create_test_userservice(
    service_pool: models.ServicePool,
    publication: models.ServicePoolPublication,
    user: models.User,
) -> models.UserService:
    user_service: 'models.UserService' = service_pool.userServices.create(
        friendly_name='user-service-{}'.format(glob['user_service_id']),
        publication=publication,
        unique_id=generators.random_mac(),
        state=types.states.State.USABLE,
        os_state=types.states.State.USABLE,
        state_date=datetime.datetime.now(),
        creation_date=datetime.datetime.now() - datetime.timedelta(minutes=30),
        user=user,
        src_hostname=generators.random_string(32),
        src_ip=generators.random_ip(),
    )
    glob['user_service_id'] += 1
    return user_service


def create_test_metapool(
    service_pools: list[models.ServicePool],
    groups: list[models.Group],
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


def create_one_cache_testing_userservice(
    provider: 'models.Provider',
    user: 'models.User',
    groups: list['models.Group'],
    type_: typing.Union[typing.Literal['managed'], typing.Literal['unmanaged']],
) -> 'models.UserService':
    from uds.services.Test.service import TestServiceCache, TestServiceNoCache
    from uds.osmanagers.Test import TestOSManager
    from uds.transports.Test import TestTransport

    service = createService(provider)

    """
    Creates several testing OS Managers
    """

    osmanager: typing.Optional['models.OSManager'] = None if type_ == 'unmanaged' else create_test_osmanager()
    transport: 'models.Transport' = create_test_transport()
    service_pool: 'models.ServicePool' = create_test_servicepool(service, osmanager, groups, [transport])
    publication: 'models.ServicePoolPublication' = create_test_publication(service_pool)

    return create_test_userservice(service_pool, publication, user)


def create_cache_testing_userservices(
    count: int = 1,
    type_: typing.Literal['managed', 'unmanaged'] = 'managed',
    user: typing.Optional['models.User'] = None,
    groups: typing.Optional[list['models.Group']] = None,
) -> list[models.UserService]:
    from . import authenticators

    if not user or not groups:
        auth = authenticators.createAuthenticator()
        groups = authenticators.createGroups(auth, 3)
        user = authenticators.createUsers(auth, 1, groups=groups)[0]
    user_services: list[models.UserService] = []
    for _ in range(count):
        user_services.append(create_one_cache_testing_userservice(createProvider(), user, groups, type_))
    return user_services
