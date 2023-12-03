"""
Created on Nov 15, 2012-2019

@author: dkmaster
"""
import logging

import typing
import collections.abc

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OVirtProvider

logger = logging.getLogger(__name__)


def getResources(parameters: typing.Any) -> list[dict[str, typing.Any]]:
    """
    This helper is designed as a callback for machine selector, so we can provide valid clusters and datastores domains based on it
    """
    from .provider import OVirtProvider
    from uds.core.environment import Environment

    logger.debug('Parameters received by getResources Helper: %s', parameters)
    env = Environment(parameters['ev'])
    provider: 'OVirtProvider' = OVirtProvider(env)
    provider.deserialize(parameters['ov'])

    # Obtains datacenter from cluster
    ci = provider.getClusterInfo(parameters['cluster'])

    res = []
    # Get storages for that datacenter
    for storage in provider.getDatacenterInfo(ci['datacenter_id'])['storage']:
        if storage['type'] == 'data':
            space, free = (
                storage['available'] + storage['used']
            ) / 1024 / 1024 / 1024, storage['available'] / 1024 / 1024 / 1024

            res.append(
                {
                    'id': storage['id'],
                    'text': "%s (%4.2f GB/%4.2f GB) %s"
                    % (
                        storage['name'],
                        space,
                        free,
                        storage['active'] and '(ok)' or '(disabled)',
                    ),
                }
            )
    data = [{'name': 'datastore', 'choices': res}]

    logger.debug('return data: %s', data)
    return data
