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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import time
import logging
import typing

from uds.core import jobs

from uds.models import Provider
from uds.core.util.model import sql_stamp_seconds
from uds.core.util.unique_id_generator import UniqueIDGenerator
import uds.services.Proxmox.proxmox.exceptions

from . import provider
from .proxmox import types as prox_types

# Note that even reseting, UDS will get always a FREE vmid, so even if the machine is already in use
# (and removed from used db), it will not be reused until it has dissapeared from the proxmox server
MAX_VMID_LIFE_SECS: typing.Final[int] = 365 * 24 * 60 * 60 * 3  # 3 years for "reseting"

logger = logging.getLogger(__name__)

# Job will be here for 4.0, but will be removed in a future
# The idea is allow using old Removal Job for existing installations
# but use new DeferredDeletionWorker for new installations


class ProxmoxDeferredRemoval(jobs.Job):
    frecuency = 60 * 3  # Once every NN minutes
    friendly_name = 'Proxmox removal'
    counter = 0
    
    def get_vmid_stored_data_from(self, data: bytes) -> typing.Tuple[int, bool]:
        vmdata = data.decode()
        if ':' in vmdata:
            vmid, try_graceful_shutdown_s = vmdata.split(':')
            try_graceful_shutdown = try_graceful_shutdown_s == 'y'
        else:
            vmid = vmdata
            try_graceful_shutdown = False
        return int(vmid), try_graceful_shutdown
        

    # @staticmethod
    # def remove(provider_instance: 'provider.ProxmoxProvider', vmid: int, try_graceful_shutdown: bool) -> None:
    #     def store_for_deferred_removal() -> None:
    #         provider_instance.storage.save_to_db('tr' + str(vmid), f'{vmid}:{"y" if try_graceful_shutdown else "n"}', attr1='tRm')
    #     ProxmoxDeferredRemoval.counter += 1
    #     logger.debug('Adding %s from %s to defeffed removal process', vmid, provider_instance)
    #     try:
    #         # First check state & stop machine if needed
    #         vminfo = provider_instance.get_machine_info(vmid)
    #         if vminfo.status == 'running':
    #             if try_graceful_shutdown:
    #                 # If running vm,  simply try to shutdown 
    #                 provider_instance.shutdown_machine(vmid)
    #                 # Store for later removal
    #             else: 
    #                 # If running vm,  simply stops it and wait for next
    #                 provider_instance.stop_machine(vmid)
                    
    #             store_for_deferred_removal()
    #             return

    #         provider_instance.remove_machine(vmid)  # Try to remove, launch removal, but check later
    #         store_for_deferred_removal()
            
    #     except client.ProxmoxNotFound:
    #         return  # Machine does not exists
    #     except Exception as e:
    #         store_for_deferred_removal()
    #         logger.info(
    #             'Machine %s could not be removed right now, queued for later: %s',
    #             vmid,
    #             e,
    #         )

    @staticmethod
    def waitForTaskFinish(
        providerInstance: 'provider.ProxmoxProvider',
        upid: 'prox_types.UPID',
        maxWait: int = 30,  # 30 * 0.3 = 9 seconds
    ) -> bool:
        counter = 0
        while providerInstance.get_task_info(upid.node, upid.upid).is_running() and counter < maxWait:
            time.sleep(0.3)
            counter += 1

        return counter < maxWait

    def run(self) -> None:
        dbProvider: Provider
        # Look for Providers of type proxmox
        for dbProvider in Provider.objects.filter(
            maintenance_mode=False, data_type=provider.ProxmoxProvider.type_type
        ):
            logger.debug('Provider %s if os type proxmox', dbProvider)

            storage = dbProvider.get_environment().storage
            instance: provider.ProxmoxProvider = typing.cast(
                provider.ProxmoxProvider, dbProvider.get_instance()
            )

            for data in storage.filter('tRm'):
                vmid, _try_graceful_shutdown = self.get_vmid_stored_data_from(data[1])
                # In fact, here, _try_graceful_shutdown is not used, but we keep it for mayby future use
                # The soft shutdown has already being initiated by the remove method
                   
                try:
                    vmInfo = instance.get_vm_info(vmid)
                    logger.debug('Found %s for removal %s', vmid, data)
                    # If machine is powered on, tries to stop it
                    # tries to remove in sync mode
                    if vmInfo.status == 'running':
                        ProxmoxDeferredRemoval.waitForTaskFinish(instance, instance.stop_machine(vmid))
                        return

                    if vmInfo.status == 'stopped':  # Machine exists, try to remove it now
                        ProxmoxDeferredRemoval.waitForTaskFinish(instance, instance.delete_vm(vmid))

                    # It this is reached, remove check
                    storage.remove('tr' + str(vmid))
                except uds.services.Proxmox.proxmox.exceptions.ProxmoxNotFound:
                    storage.remove('tr' + str(vmid))  # VM does not exists anymore
                except Exception as e:  # Any other exception wil be threated again
                    # instance.log('Delayed removal of %s has failed: %s. Will retry later', vmId, e)
                    logger.error('Delayed removal of %s failed: %s', data, e)

        logger.debug('Deferred removal for proxmox finished')


class ProxmoxVmidReleaser(jobs.Job):
    frecuency = 60 * 60 * 24 * 30  # Once a month
    friendly_name = 'Proxmox maintenance'

    def run(self) -> None:
        logger.debug('Proxmox Vmid releader running')
        gen = UniqueIDGenerator('proxmoxvmid', 'proxmox')
        gen.release_older_than(sql_stamp_seconds() - MAX_VMID_LIFE_SECS)
