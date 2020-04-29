#
# Copyright (c) 2012-2020 Virtual Cable S.L.
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
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
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
import time
import logging
import typing

from uds.core import jobs

from uds.models import Provider

from . import provider
from . import client

# Not imported at runtime, just for type checking

logger = logging.getLogger(__name__)

class ProxmoxDeferredRemoval(jobs.Job):
    frecuency = 60 * 5  # Once every NN minutes
    friendly_name = 'Proxmox removal'
    counter = 0

    @staticmethod
    def remove(providerInstance: 'provider.ProxmoxProvider', vmId: int) -> None:
        logger.debug('Adding %s from %s to defeffed removal process', vmId, providerInstance)
        ProxmoxDeferredRemoval.counter += 1
        try:
            # First check state & stop machine if needed
            vmInfo = providerInstance.getMachineInfo(vmId)
            if vmInfo.status == 'running':
                # If running vm,  simply stops it and wait for next 
                ProxmoxDeferredRemoval.waitForTaskFinish(providerInstance, providerInstance.stopMachine(vmId))

            ProxmoxDeferredRemoval.waitForTaskFinish(providerInstance, providerInstance.removeMachine(vmId))
        except client.ProxmoxNotFound:
            return  # Machine does not exists
        except Exception as e:
            providerInstance.storage.saveData('tr' + str(vmId), str(vmId), attr1='tRm')
            logger.info('Machine %s could not be removed right now, queued for later: %s', vmId, e)

    @staticmethod
    def waitForTaskFinish(providerInstance: 'provider.ProxmoxProvider', upid: 'client.types.UPID', maxWait: int = 30) -> bool:
        counter = 0
        while providerInstance.getTaskInfo(upid.node, upid.upid).isRunning() and counter < maxWait:
            time.sleep(0.3)
            counter += 1
        
        return counter < maxWait

    def run(self) -> None:
        dbProvider: Provider
        # Look for Providers of type proxmox
        for dbProvider in Provider.objects.filter(maintenance_mode=False, data_type=provider.ProxmoxProvider.typeType):
            logger.debug('Provider %s if os type proxmox', dbProvider)

            storage = dbProvider.getEnvironment().storage
            instance: provider.ProxmoxProvider = typing.cast(provider.ProxmoxProvider, dbProvider.getInstance())

            for i in storage.filter('tRm'):
                vmId = int(i[1].decode())
                
                try:
                    vmInfo = instance.getMachineInfo(vmId)
                    logger.debug('Found %s for removal %s', vmId, i)
                    # If machine is powered on, tries to stop it
                    # tries to remove in sync mode
                    if vmInfo.status == 'running':
                        ProxmoxDeferredRemoval.waitForTaskFinish(instance, instance.stopMachine(vmId))
                        return

                    if vmInfo.status == 'stopped':  # Machine exists, try to remove it now
                        ProxmoxDeferredRemoval.waitForTaskFinish(instance, instance.removeMachine(vmId))


                    # It this is reached, remove check
                    storage.remove('tr' + str(vmId))
                except client.ProxmoxNotFound:
                    storage.remove('tr' + str(vmId))  # VM does not exists anymore
                except Exception as e:  # Any other exception wil be threated again
                    # instance.doLog('Delayed removal of %s has failed: %s. Will retry later', vmId, e)
                    logger.error('Delayed removal of %s failed: %s', i, e)

        logger.debug('Deferred removal for proxmox finished')
