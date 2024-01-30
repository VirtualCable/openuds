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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import collections.abc
import logging
from multiprocessing import pool
import typing

from django.utils.translation import gettext as _

from uds.core import types
from uds.core.environment import Environment
from uds.core.ui.user_interface import gui
from uds import models
from uds.services.OpenNebula.on import vm

logger = logging.getLogger(__name__)


def get_storage(parameters: typing.Any) -> types.ui.CallbackResultType:
    from .provider import ProxmoxProvider  # pylint: disable=import-outside-toplevel

    logger.debug('Parameters received by getResources Helper: %s', parameters)
    provider = typing.cast(
        ProxmoxProvider, models.Provider.objects.get(uuid=parameters['prov_uuid']).get_instance()
    )

    # Obtains datacenter from cluster
    try:
        vm_info = provider.get_machine_info(int(parameters['machine']))
    except Exception:
        return []

    res = []
    # Get storages for that datacenter
    for storage in sorted(provider.list_storages(vm_info.node), key=lambda x: int(not x.shared)):
        if storage.type in ('lvm', 'iscsi', 'iscsidirect'):
            continue
        space, free = (
            storage.avail / 1024 / 1024 / 1024,
            (storage.avail - storage.used) / 1024 / 1024 / 1024,
        )
        extra = _(' shared') if storage.shared else _(' (bound to {})').format(vm_info.node)
        res.append(
            gui.choice_item(storage.storage, f'{storage.storage} ({space:4.2f} GB/{free:4.2f} GB){extra}')
        )

    data: types.ui.CallbackResultType = [{'name': 'datastore', 'choices': res}]

    logger.debug('return data: %s', data)
    return data


def get_machines(parameters: typing.Any) -> types.ui.CallbackResultType:
    from .provider import ProxmoxProvider  # pylint: disable=import-outside-toplevel

    logger.debug('Parameters received by getResources Helper: %s', parameters)
    provider = typing.cast(
        ProxmoxProvider, models.Provider.objects.get(uuid=parameters['prov_uuid']).get_instance()
    )

    # Obtains datacenter from cluster
    try:
        pool_info = provider.get_pool_info(parameters['pool'], retrieve_vm_names=True)
    except Exception:
        return []

    return [
        {
            'name': 'machines',
            'choices': [gui.choice_item(member.vmid, member.vmname) for member in pool_info.members],
        }
    ]
