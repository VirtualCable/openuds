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
# pyright: reportUnknownMemberType=false, reportAttributeAccessIssue=false

import contextlib
import threading
import logging
import typing
import collections.abc
import ssl  # for getting server certificate

import ovirtsdk4
import ovirtsdk4.types

from uds.core import consts, types
from uds.core.util import decorators

from . import types as ov_types

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.cache import Cache

logger = logging.getLogger(__name__)

_lock = threading.Lock()
USE_LOCK: typing.Final[bool] = False


@contextlib.contextmanager
def _access_lock() -> typing.Generator[None, None, None]:
    if USE_LOCK:
        _lock.acquire()
    try:
        yield
    finally:
        if USE_LOCK:
            _lock.release()


def _key_helper(obj: 'Client') -> str:
    return obj._host + obj._username


class Client:
    """
    Module to manage oVirt connections using ovirtsdk.

    Due to the fact that we can't create two proxy connections at same time, we serialize all access to ovirt platform.
    Only one request and one live connection can exists at a time.

    This can waste a lot of time, so use of cache here is more than important to achieve aceptable performance.

    """

    _host: str
    _username: str
    _password: str
    _timeout: int
    _cache: 'Cache'

    _api: typing.Optional[ovirtsdk4.Connection] = None

    @property
    def api(self) -> ovirtsdk4.Connection:
        """
        Gets the api connection.

        Again, due to the fact that ovirtsdk don't allow (at this moment, but it's on the "TODO" list) concurrent access to
        more than one server, we keep only one opened connection.

        Must be accesed "locked", so we can safely alter cached_api and cached_api_key
        """
        # if cached_api_key == aKey:
        #    return cached_api

        if self._api is None:
            try:
                self._api = ovirtsdk4.Connection(
                    url='https://' + self._host + '/ovirt-engine/api',
                    username=self._username,
                    password=self._password,
                    timeout=self._timeout,
                    insecure=True,
                )  # , debug=True, log=logger )
            except Exception as e:
                self._api = None
                logger.exception('Exception on ovirt connection at %s', self._host)
                raise Exception('Error connecting to oVirt: {}'.format(e)) from e

        return self._api

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: int,
        cache: 'Cache',
    ):
        self._host = host
        self._username = username
        self._password = password
        self._timeout = int(timeout)
        self._cache = cache

    def test(self) -> bool:
        try:
            with _access_lock():
                return self.api.test()
        except Exception as e:
            logger.error('Testing Server failed for oVirt: %s', e)
            return False

    @decorators.cached(prefix='o-vms', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=_key_helper)
    def list_machines(self, **kwargs: typing.Any) -> list[ov_types.VMInfo]:
        """
        Obtains the list of machines inside ovirt that do aren't part of uds

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'cluster_id'

        """
        with _access_lock():
            return [
                ov_types.VMInfo.from_data(vm)
                for vm in typing.cast(list[typing.Any], self.api.system_service().vms_service().list())
            ]

    @decorators.cached(prefix='o-vm', timeout=consts.cache.SMALLEST_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_machine_info(self, machine_id: str, **kwargs: typing.Any) -> ov_types.VMInfo:
        with _access_lock():
            try:
                return ov_types.VMInfo.from_data(
                    typing.cast(typing.Any, self.api.system_service().vms_service().service(machine_id).get())
                )
            except Exception:
                return ov_types.VMInfo.missing()

    @decorators.cached(prefix='o-clusters', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=_key_helper)
    def list_clusters(self, **kwargs: typing.Any) -> list[ov_types.ClusterInfo]:
        """
        Obtains the list of clusters inside ovirt

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        """
        with _access_lock():
            return [
                ov_types.ClusterInfo.from_data(cluster)
                for cluster in typing.cast(
                    list[typing.Any], self.api.system_service().clusters_service().list()
                )
            ]

    @decorators.cached(prefix='o-cluster', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_cluster_info(self, cluster_id: str, **kwargs: typing.Any) -> ov_types.ClusterInfo:
        """
        Obtains the cluster info

        Args:
            datacenterId: Id of the cluster to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        """
        with _access_lock():
            return ov_types.ClusterInfo.from_data(
                typing.cast(typing.Any, self.api.system_service().clusters_service().service(cluster_id).get())
            )

    @decorators.cached(prefix='o-dc', timeout=consts.cache.LONG_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_datacenter_info(self, datacenter_id: str, **kwargs: typing.Any) -> ov_types.DatacenterInfo:
        """
        Obtains the datacenter info

        Args:
            datacenterId: Id of the datacenter to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns:
            the datacenter info on a DatacenterInfo object


        """
        with _access_lock():
            datacenter_service: typing.Any = (
                self.api.system_service().data_centers_service().service(datacenter_id)
            )

            data: typing.Any = datacenter_service.get()

            return ov_types.DatacenterInfo.from_data(
                data,
                [
                    ov_types.StorageInfo.from_data(s)
                    for s in datacenter_service.storage_domains_service().list()
                ],
            )

    @decorators.cached(prefix='o-str', timeout=consts.cache.SHORT_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_storage_info(self, storage_id: str, **kwargs: typing.Any) -> ov_types.StorageInfo:
        """
        Obtains the datacenter info

        Args:
            storageId: Id of the storage to get information about it

        Returns:
            the storage info on a StorageInfo object
        """
        with _access_lock():
            return ov_types.StorageInfo.from_data(
                typing.cast(
                    typing.Any, self.api.system_service().storage_domains_service().service(storage_id).get()
                )
            )

    def create_template(
        self,
        name: str,
        comments: str,
        machine_id: str,
        cluster_id: str,
        storage_id: str,
        display_type: str,
    ) -> ov_types.TemplateInfo:
        """
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            name: Name of the machine (care, only ascii characters and no spaces!!!)
            machineId: id of the machine to be published
            clusterId: id of the cluster that will hold the machine
            storageId: id of the storage tuat will contain the publication AND linked clones
            displayType: type of display (for oVirt admin interface only)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.
        """
        logger.debug(
            "n: %s, c: %s, vm: %s, cl: %s, st: %s, dt: %s",
            name,
            comments,
            machine_id,
            cluster_id,
            storage_id,
            display_type,
        )

        with _access_lock():
            # cluster = ov.clusters_service().service('00000002-0002-0002-0002-0000000002e4') # .get()
            # vm = ov.vms_service().service('e7ff4e00-b175-4e80-9c1f-e50a5e76d347') # .get()

            vms: typing.Any = self.api.system_service().vms_service().service(machine_id)

            cluster: typing.Any = typing.cast(
                typing.Any, self.api.system_service().clusters_service().service(cluster_id).get()
            )
            vm: typing.Any = vms.get()  # pyright: ignore

            if vm is None:
                raise Exception('Machine not found')

            if cluster is None:
                raise Exception('Cluster not found')

            if vm.status.value != 'down':
                raise Exception('Machine must be powered off to publish it')

            # sd = [ovirtsdk4.types.StorageDomain(id=storageId)]
            # dsks = []
            # for dsk in vms.disk_attachments_service().list():
            #    dsks = None
            # dsks.append(params.Disk(id=dsk.get_id(), storage_domains=sd, alias=dsk.get_alias()))
            # dsks.append(dsk)

            tvm = ovirtsdk4.types.Vm(id=vm.id)
            tcluster = ovirtsdk4.types.Cluster(id=cluster.id)

            template = ovirtsdk4.types.Template(name=name, vm=tvm, cluster=tcluster, description=comments)

            # display=display)
            return ov_types.TemplateInfo.from_data(
                typing.cast(
                    ovirtsdk4.types.Template,
                    self.api.system_service().templates_service().add(template),
                )
            )

    @decorators.cached(prefix='o-templates', timeout=consts.cache.DEFAULT_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_template_info(self, template_id: str) -> ov_types.TemplateInfo:
        """
        Returns the template info for the given template id
        """
        with _access_lock():
            try:
                return ov_types.TemplateInfo.from_data(
                    typing.cast(
                        ovirtsdk4.types.Template,
                        self.api.system_service().templates_service().service(template_id).get(),
                    )
                )
            except Exception:  # Not found
                return ov_types.TemplateInfo.missing()

    def deploy_from_template(
        self,
        name: str,
        comments: str,
        template_id: str,
        cluster_id: str,
        display_type: str,
        usb_type: str,
        memory_mb: int,
        guaranteed_mb: int,
    ) -> ov_types.VMInfo:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad oVirt admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        """
        logger.debug(
            'Deploying machine with name "%s" from template %s at cluster %s with display %s and usb %s, memory %s and guaranteed %s',
            name,
            template_id,
            cluster_id,
            display_type,
            usb_type,
            memory_mb,
            guaranteed_mb,
        )
        with _access_lock():
            logger.debug('Deploying machine %s', name)

            cluster = ovirtsdk4.types.Cluster(id=cluster_id)
            template = ovirtsdk4.types.Template(id=template_id)

            # Create initally the machine without usb support, will be added later
            usb = ovirtsdk4.types.Usb(enabled=False)

            memoryPolicy = ovirtsdk4.types.MemoryPolicy(guaranteed=guaranteed_mb * 1024 * 1024)
            par = ovirtsdk4.types.Vm(
                name=name,
                cluster=cluster,
                template=template,
                description=comments,
                type=ovirtsdk4.types.VmType.DESKTOP,
                memory=memory_mb * 1024 * 1024,
                memory_policy=memoryPolicy,
                usb=usb,
            )  # display=display,

            return ov_types.VMInfo.from_data(self.api.system_service().vms_service().add(par))

    def remove_template(self, template_id: str) -> None:
        """
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        """
        with _access_lock():
            self.api.system_service().templates_service().service(template_id).remove()
            # This returns nothing, if it fails it raises an exception

    @decorators.cached(
        prefix='o-templates', timeout=consts.cache.SMALLEST_CACHE_TIMEOUT, key_helper=_key_helper
    )
    def list_snapshots(self, machine_id: str) -> list[ov_types.SnapshotInfo]:
        """
        Lists the snapshots of the given machine
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            return [
                ov_types.SnapshotInfo.from_data(s)
                for s in typing.cast(list[typing.Any], vm_service.snapshots_service().list())
            ]

    @decorators.cached(prefix='o-snapshot', timeout=consts.cache.SMALLEST_CACHE_TIMEOUT, key_helper=_key_helper)
    def get_snapshot_info(self, machine_id: str, snapshot_id: str) -> ov_types.SnapshotInfo:
        """
        Returns the snapshot info for the given snapshot id
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            return ov_types.SnapshotInfo.from_data(
                typing.cast(
                    ovirtsdk4.types.Snapshot,
                    vm_service.snapshots_service().service(snapshot_id).get(),
                )
            )

    def create_snapshot(
        self, machine_id: str, snapshot_name: str, snapshot_description: str
    ) -> ov_types.SnapshotInfo:
        """
        Creates a snapshot of the machine with the given name and description
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            snapshot = ovirtsdk4.types.Snapshot(
                name=snapshot_name, description=snapshot_description, persist_memorystate=True
            )
            return ov_types.SnapshotInfo.from_data(vm_service.snapshots_service().add(snapshot))

    def remove_snapshot(self, machine_id: str, snapshot_id: str) -> None:
        """
        Removes the snapshot with the given id
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            vm_service.snapshots_service().service(snapshot_id).remove()

    def start_machine(self, machine_id: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            vm_service.start()

    def stop_machine(self, machine_id: str) -> None:
        """
        Tries to stop a machine. No check is done, it is simply requested to oVirt

        Args:
            machine_id: Id of the machine

        Returns:
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            vm_service.stop()
            
    def shutdown_machine(self, machine_id: str) -> None:
        """
        Tries to shutdown a machine. No check is done, it is simply requested to oVirt

        Args:
            machine_id: Id of the machine

        Returns:
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            vm_service.shutdown()

    def suspend_machine(self, machine_id: str) -> None:
        """
        Tries to suspend a machine. No check is done, it is simply requested to oVirt

        Args:
            machine_id: Id of the machine

        Returns:
        """
        with _access_lock():
            vmService: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.suspend()

    def remove_machine(self, machine_id: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        with _access_lock():
            vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            vm_service.remove()

    def update_machine_mac(self, machine_id: str, mac: str) -> None:
        """
        Changes the mac address of first nic of the machine to the one specified
        """
        with _access_lock():
            try:
                vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)

                if vm_service.get() is None:
                    raise Exception('Machine not found')

                nic = vm_service.nics_service().list()[0]  # If has no nic, will raise an exception (IndexError)
                nic.mac.address = mac
                nicService = vm_service.nics_service().service(nic.id)
                nicService.update(nic)
            except IndexError:
                raise Exception('Machine do not have network interfaces!!')

    def fix_usb(self, machine_id: str) -> None:
        # Fix for usb support
        with _access_lock():
            usb = ovirtsdk4.types.Usb(enabled=True, type=ovirtsdk4.types.UsbType.NATIVE)
            vms: typing.Any = self.api.system_service().vms_service().service(machine_id)
            vmu = ovirtsdk4.types.Vm(usb=usb)
            vms.update(vmu)

    def get_console_connection_info(
        self, machine_id: str
    ) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        """
        Gets the connetion info for the specified machine
        """
        with _access_lock():
            try:
                vm_service: typing.Any = self.api.system_service().vms_service().service(machine_id)
                vm = vm_service.get()

                if vm is None:
                    raise Exception('Machine not found')

                display = vm.display
                ticket = vm_service.ticket()

                ca: str = ''  # Not known ca
                # Get host subject
                cert_subject = ''
                if display.certificate is not None:
                    cert_subject = display.certificate.subject
                    ca = display.certificate.content
                else:
                    for i in typing.cast(
                        collections.abc.Iterable[typing.Any], self.api.system_service().hosts_service().list()
                    ):
                        for k in typing.cast(
                            collections.abc.Iterable[typing.Any],
                            self.api.system_service()
                            .hosts_service()
                            .service(i.id)
                            .nics_service()  # pyright: ignore
                            .list(),
                        ):
                            if k.ip.address == display.address:
                                cert_subject = i.certificate.subject
                                break
                        # If found
                        if cert_subject != '':
                            break
                    # Try to get certificate from host
                    # Note: This will only work if the certificate is self-signed
                    try:
                        ca = ssl.get_server_certificate((display.address, display.secure_port))
                    except Exception:
                        ca = ''

                return types.services.ConsoleConnectionInfo(
                    type=display.type.value,
                    address=display.address,
                    port=display.port,
                    secure_port=display.secure_port,
                    cert_subject=cert_subject,
                    ca=ca,
                    ticket=types.services.ConsoleConnectionTicket(value=ticket.value),
                )

            except Exception:
                return None
