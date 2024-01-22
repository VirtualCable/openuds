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
import logging
import typing
import collections.abc

from uds.core.environment import Environment 

from django.utils.translation import gettext as _


logger = logging.getLogger(__name__)


def get_storage(parameters: typing.Any) -> list[dict[str, typing.Any]]:
    from .provider import ProxmoxProvider  # pylint: disable=import-outside-toplevel

    logger.debug('Parameters received by getResources Helper: %s', parameters)
    env = Environment(parameters['ev'])
    provider: ProxmoxProvider = ProxmoxProvider(env)
    provider.deserialize(parameters['ov'])

    # Obtains datacenter from cluster
    try:
        vmInfo = provider.getMachineInfo(int(parameters['machine']))
    except Exception:
        return []

    res = []
    # Get storages for that datacenter
    for storage in sorted(
        provider.listStorages(vmInfo.node), key=lambda x: int(not x.shared)
    ):
        if storage.type in ('lvm', 'iscsi', 'iscsidirect'):
            continue
        space, free = (
            storage.avail / 1024 / 1024 / 1024,
            (storage.avail - storage.used) / 1024 / 1024 / 1024,
        )
        extra = (
            _(' shared') if storage.shared else _(' (bound to {})').format(vmInfo.node)
        )
        res.append(
            {
                'id': storage.storage,
                'text': "%s (%4.2f GB/%4.2f GB)%s"
                % (storage.storage, space, free, extra),
            }
        )

    data = [{'name': 'datastore', 'choices': res}]

    logger.debug('return data: %s', data)
    return data
