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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from uds.core import jobs

from uds.models import Provider

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OVirtProvider

logger = logging.getLogger(__name__)


class OVirtHouseKeeping(jobs.Job):
    frecuency = 60 * 60 * 24 * 15 + 1  # Once every 15 days
    friendly_name = 'Ovirt house keeping'

    def run(self):
        return


class OVirtDeferredRemoval(jobs.Job):
    frecuency = 60 * 5  # Once every NN minutes
    friendly_name = 'Ovirt removal'
    counter = 0

    @staticmethod
    def remove(providerInstance: 'OVirtProvider', vmId: str) -> None:
        logger.debug(
            'Adding %s from %s to defeffed removal process', vmId, providerInstance
        )
        OVirtDeferredRemoval.counter += 1
        try:
            # Tries to stop machine sync when found, if any error is done, defer removal for a scheduled task
            try:
                # First check state & stop machine if needed
                state = providerInstance.getMachineState(vmId)
                if state in ('up', 'powering_up', 'suspended'):
                    providerInstance.stopMachine(vmId)
                elif state != 'unknown':  # Machine exists, remove it later
                    providerInstance.storage.saveData('tr' + vmId, vmId, attr1='tRm')

            except Exception as e:
                providerInstance.storage.saveData('tr' + vmId, vmId, attr1='tRm')
                logger.info(
                    'Machine %s could not be removed right now, queued for later: %s',
                    vmId,
                    e,
                )

        except Exception as e:
            logger.warning('Exception got queuing for Removal: %s', e)

    def run(self) -> None:
        from .provider import OVirtProvider

        logger.debug('Looking for deferred vm removals')

        provider: Provider
        # Look for Providers of type Ovirt
        for provider in Provider.objects.filter(
            maintenance_mode=False, data_type=OVirtProvider.typeType
        ):
            logger.debug('Provider %s if os type ovirt', provider)

            storage = provider.getEnvironment().storage
            instance: OVirtProvider = typing.cast(OVirtProvider, provider.getInstance())

            for i in storage.filter('tRm'):
                vmId = i[1].decode()
                try:
                    logger.debug('Found %s for removal %s', vmId, i)
                    # If machine is powered on, tries to stop it
                    # tries to remove in sync mode
                    state = instance.getMachineState(vmId)
                    if state in ('up', 'powering_up', 'suspended'):
                        instance.stopMachine(vmId)
                        return

                    if state != 'unknown':  # Machine exists, try to remove it now
                        instance.removeMachine(vmId)

                    # It this is reached, remove check
                    storage.remove('tr' + vmId)
                except Exception as e:  # Any other exception wil be threated again
                    # instance.doLog('Delayed removal of %s has failed: %s. Will retry later', vmId, e)
                    logger.error('Delayed removal of %s failed: %s', i, e)

        logger.debug('Deferred removal finished')
