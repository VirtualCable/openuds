# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from uds.core import jobs

from uds.models import Provider
from .ovirt import types as ov_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OVirtProvider

logger = logging.getLogger(__name__)


# class OVirtHouseKeeping(jobs.Job):
#     frecuency = 60 * 60 * 24 * 15 + 1  # Once every 15 days
#     friendly_name = 'Ovirt house keeping'
#
#     def run(self) -> None:
#         pass


class OVirtDeferredRemoval(jobs.Job):
    frecuency = 60 * 5  # Once every NN minutes
    friendly_name = 'Ovirt removal'
    counter = 0

    @staticmethod
    def remove(instance: 'OVirtProvider', vmid: str) -> None:
        logger.debug('Adding %s from %s to defeffed removal process', vmid, instance)
        OVirtDeferredRemoval.counter += 1
        try:
            # Tries to stop machine sync when found, if any error is done, defer removal for a scheduled task
            try:
                # First check state & stop machine if needed
                status = instance.api.get_machine_info(vmid).status
                if status in (ov_types.VMStatus.UP, ov_types.VMStatus.POWERING_UP, ov_types.VMStatus.SUSPENDED):
                    instance.api.stop_machine(vmid)
                elif status != ov_types.VMStatus.UNKNOWN:  # Machine exists, remove it later
                    instance.storage.save_to_db('tr' + vmid, vmid, attr1='tRm')

            except Exception as e:
                instance.storage.save_to_db('tr' + vmid, vmid, attr1='tRm')
                logger.info(
                    'Machine %s could not be removed right now, queued for later: %s',
                    vmid,
                    e,
                )

        except Exception as e:
            logger.warning('Exception got queuing for Removal: %s', e)

    def run(self) -> None:
        from .provider import OVirtProvider

        logger.debug('Looking for deferred vm removals')

        # Look for Providers of type Ovirt
        for provider in Provider.objects.filter(maintenance_mode=False, data_type=OVirtProvider.type_type):
            logger.debug('Provider %s if os type ovirt', provider)

            storage = provider.get_environment().storage
            instance: OVirtProvider = typing.cast(OVirtProvider, provider.get_instance())

            for i in storage.filter('tRm'):
                vmid = i[1].decode()
                try:
                    logger.debug('Found %s for removal %s', vmid, i)
                    # If machine is powered on, tries to stop it
                    # tries to remove in sync mode
                    status = instance.api.get_machine_info(vmid).status
                    if status in (
                        ov_types.VMStatus.UP,
                        ov_types.VMStatus.POWERING_UP,
                        ov_types.VMStatus.SUSPENDED,
                    ):
                        instance.api.stop_machine(vmid)
                        return

                    if status != ov_types.VMStatus.UNKNOWN:  # Machine exists, try to remove it now
                        instance.api.remove_machine(vmid)

                    # It this is reached, remove check
                    storage.remove('tr' + vmid)
                except Exception as e:  # Any other exception wil be threated again
                    # instance.log('Delayed removal of %s has failed: %s. Will retry later', vmId, e)
                    logger.error('Delayed removal of %s failed: %s', i, e)

        logger.debug('Deferred removal finished')
