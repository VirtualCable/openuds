"""
Created on Nov 15, 2012-2019

@author: dkmaster
"""

import logging

import typing

from uds import models
from uds.core import types
from uds.core.ui.user_interface import gui

from .ovirt import types as ov_types

if typing.TYPE_CHECKING:
    from .ovirt import client

logger = logging.getLogger(__name__)


def get_api(parameters: typing.Any) -> 'client.Client':
    """
    Helper to get an API client
    """
    from .provider import OVirtProvider

    logger.debug('Parameters received by getResources Helper: %s', parameters)
    return typing.cast(
        OVirtProvider, models.Provider.objects.get(uuid=parameters['prov_uuid']).get_instance()
    ).api


def get_resources(parameters: typing.Any) -> types.ui.CallbackResultType:
    """
    This helper is designed as a callback for machine selector, so we can provide valid clusters and datastores domains based on it
    """
    api = get_api(parameters)

    logger.debug('Parameters received by getResources Helper: %s', parameters)

    # Obtains datacenter from cluster
    ci = api.get_cluster_info(parameters['cluster'])

    res: list[types.ui.ChoiceItem] = []
    # Get storages for that datacenter
    for storage in api.get_datacenter_info(ci.datacenter_id).storage:
        if storage.type == ov_types.StorageType.DATA:
            space, free = (
                storage.available + storage.used
            ) / 1024 / 1024 / 1024, storage.available / 1024 / 1024 / 1024

            res.append(
                gui.choice_item(
                    storage.id,
                    f'{storage.name} ({space:4.2f} GB/{free:4.2f} GB) {storage.enabled and "(ok)" or "(disabled)"}',
                )
            )
    data: types.ui.CallbackResultType = [{'name': 'datastore', 'choices': res}]

    logger.debug('return data: %s', data)
    return data
