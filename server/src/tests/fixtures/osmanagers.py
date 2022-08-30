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
import typing

from uds import models
from uds.core import environment
from uds.core.util import states
from uds.core.managers.crypto import CryptoManager

# Counters so we can reinvoke the same method and generate new data
glob = {
    'service_id': 0,
    'service_pool_id': 0,
    'user_service_id': 0,
}

def createProvider(
    provider: typing.Optional[models.Provider] = None,
) -> models.Provider:
    """
    Creates a testing provider
    """
    if provider is None:
        from uds.services.Test.provider import TestProvider

        provider = models.Provider()
        provider.name = 'Testing provider'
        provider.comments = 'Tesging provider'
        provider.data_type = TestProvider.typeType
        provider.data = provider.getInstance().serialize()
        provider.save()

    return provider


def createServices(
    provider: 'models.Provider',
    number_of_services: int = 1,
    type_of_service: typing.Union[typing.Literal['cache'], typing.Literal['nocache']] = 'cache',
) -> typing.List[models.Service]:
    """
    Creates a number of services
    """
    from uds.services.Test.service import TestServiceCache, TestServiceNoCache
    service_type = TestServiceCache if type_of_service == 'cache' else TestServiceNoCache

    services = []
    for i in range(number_of_services):
        service: 'models.Service' = provider.services.create(
            name='Service %d' % (glob['service_id']),
            data_type=service_type.typeType,
            data=service_type(environment.Environment(str(glob['service_id'])), provider.getInstance()).serialize(),
            token='token%d' % (glob['service_id']),
        )
        glob['service_id'] += 1
        services.append(service)
    return services

def createServicePools(
    service: 'models.Service',
    os_manager: typing.Optional['models.OSManager'] = None,
    transports: typing.Optional[typing.List['models.Transport']] = None,
    groups: typing.Optional[typing.List['models.Group']] = None,
    number_of_pool_services: int = 1,
) -> typing.List[models.ServicePool]:
    """
    Creates a number of service pools
    """
    service_pools = []
    for i in range(number_of_pool_services):
        service_pool: 'models.ServicePool' = service.deployedServices.create(
            name='Service pool %d' % (glob['service_pool_id']),
            short_name='pool%d' % (glob['service_pool_id']),
            comments='Comment for service pool %d' % (glob['service_pool_id']),
            osmanager=os_manager,
            transports=transports,
            assignedGroups=groups,
            # Rest of fields are left as default
        )
        glob['service_pool_id'] += 1
        service_pools.append(service_pool)
    return service_pools

def createUserServices(
    service: 'models.Service',
    in_cache: bool = False,
    user: typing.Optional[models.User] = None,
    number_of_user_services: int = 1,
) -> typing.List[models.UserService]:
    """
    Creates a number of user services
    """
    return []