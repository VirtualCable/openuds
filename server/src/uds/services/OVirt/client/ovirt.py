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

import threading
import logging
import typing
import collections.abc

import ovirtsdk4 as ovirt

from uds.core import types

# Sometimes, we import ovirtsdk4 but "types" does not get imported... event can't be found????
# With this seems to work propertly
try:
    from ovirtsdk4 import types as ovirtTypes  # pyright: ignore[reportUnusedImport]
except Exception:  # nosec just to bring on the types if they exist
    pass

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.cache import Cache

logger = logging.getLogger(__name__)

lock = threading.Lock()


class Client:
    """
    Module to manage oVirt connections using ovirtsdk.

    Due to the fact that we can't create two proxy connections at same time, we serialize all access to ovirt platform.
    Only one request and one live connection can exists at a time.

    This can waste a lot of time, so use of cache here is more than important to achieve aceptable performance.

    """

    cached_api: typing.ClassVar[typing.Optional[ovirt.Connection]] = None
    cached_api_key: typing.ClassVar[typing.Optional[str]] = None

    CACHE_TIME_LOW = 60 * 5  # Cache time for requests are 5 minutes by default
    CACHE_TIME_HIGH = (
        60 * 30
    )  # Cache time for requests that are less probable to change (as cluster perteinance of a machine)

    _host: str
    _username: str
    _password: str
    _timeout: int
    _cache: 'Cache'
    _needs_usb_fix = True

    def _generate_key(self, prefix: str = '') -> str:
        """
        Creates a key for the cache, using the prefix indicated as part of it

        Returns:
            The cache key, taking into consideration the prefix
        """
        return "{}{}{}{}{}".format(prefix, self._host, self._username, self._password, self._timeout)

    def _api(self) -> ovirt.Connection:
        """
        Gets the api connection.

        Again, due to the fact that ovirtsdk don't allow (at this moment, but it's on the "TODO" list) concurrent access to
        more than one server, we keep only one opened connection.

        Must be accesed "locked", so we can safely alter cached_api and cached_api_key
        """
        the_key = self._generate_key('o-host')
        # if cached_api_key == aKey:
        #    return cached_api

        if Client.cached_api:
            try:
                Client.cached_api.close()
            except Exception:  # nosec: this is a "best effort" close
                # Nothing happens, may it was already disconnected
                pass
        try:
            Client.cached_api_key = the_key
            Client.cached_api = ovirt.Connection(
                url='https://' + self._host + '/ovirt-engine/api',
                username=self._username,
                password=self._password,
                timeout=self._timeout,
                insecure=True,
            )  # , debug=True, log=logger )

            return Client.cached_api
        except:
            logger.exception('Exception connection ovirt at %s', self._host)
            Client.cached_api = None
            Client.cached_api_key = None
            raise Exception("Can't connet to server at {}".format(self._host))

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        timeout: typing.Union[str, int],
        cache: 'Cache',
    ):
        self._host = host
        self._username = username
        self._password = password
        self._timeout = int(timeout)
        self._cache = cache
        self._needs_usb_fix = True

    def test(self) -> bool:
        try:
            lock.acquire(True)
            return self._api().test()
        except Exception as e:
            logger.error('Testing Server failed for oVirt: %s', e)
            return False
        finally:
            lock.release()

    def is_fully_functional_version(self) -> types.core.TestResult:
        """
        '4.0 version is always functional (right now...)
        """
        return types.core.TestResult(True)

    def list_machines(self, force: bool = False) -> list[collections.abc.MutableMapping[str, typing.Any]]:
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
        vmsKey = self._generate_key('o-vms')
        val: typing.Optional[typing.Any] = self._cache.get(vmsKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self._api()

            vms: collections.abc.Iterable[typing.Any] = (
                api.system_service().vms_service().list()
            )  # pyright: ignore

            logger.debug('oVirt VMS: %s', vms)

            res: list[collections.abc.MutableMapping[str, typing.Any]] = []

            for vm in vms:
                try:
                    pair = [vm.usb.enabled, vm.usb.type.value]
                except Exception:
                    pair = [False, '']
                res.append(
                    {
                        'name': vm.name,
                        'id': vm.id,
                        'cluster_id': vm.cluster.id,
                        'usb': pair,
                    }
                )

            self._cache.put(vmsKey, res, Client.CACHE_TIME_LOW)

            return res

        finally:
            lock.release()

    def list_clusters(self, force: bool = False) -> list[collections.abc.MutableMapping[str, typing.Any]]:
        """
        Obtains the list of clusters inside ovirt

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            Filters out clusters not attached to any datacenter
            An array of dictionaries, containing:
                'name'
                'id'
                'datacenter_id'

        """
        clsKey = self._generate_key('o-clusters')
        val: typing.Optional[typing.Any] = self._cache.get(clsKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self._api()

            clusters: list[typing.Any] = api.system_service().clusters_service().list()  # pyright: ignore

            res: list[collections.abc.MutableMapping[str, typing.Any]] = []

            cluster: typing.Any
            for cluster in clusters:
                dc = cluster.data_center

                val = {
                    'name': cluster.name,
                    'id': cluster.id,
                    'datacenter_id': dc.id if dc else None,
                }

                # Updates cache info for every single cluster
                clKey = self._generate_key('o-cluster' + cluster.id)
                self._cache.put(clKey, val)

                if dc is not None:
                    res.append(val)

            self._cache.put(clsKey, res, Client.CACHE_TIME_HIGH)

            return res

        finally:
            lock.release()

    def get_cluster_info(
        self, clusterId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the cluster info

        Args:
            datacenterId: Id of the cluster to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'datacenter_id'
        """
        clKey = self._generate_key('o-cluster' + clusterId)
        val = self._cache.get(clKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self._api()

            c: typing.Any = api.system_service().clusters_service().service(clusterId).get()  # pyright: ignore

            dc = c.data_center

            if dc is not None:
                dc = dc.id

            res = {'name': c.name, 'id': c.id, 'datacenter_id': dc}
            self._cache.put(clKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()

    def get_datacenter_info(
        self, datacenterId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the datacenter info

        Args:
            datacenterId: Id of the datacenter to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'storage_type' -> ('isisi', 'nfs', ....)
                'description'
                'storage' -> array of dictionaries, with:
                   'id' -> Storage id
                   'name' -> Storage name
                   'type' -> Storage type ('data', 'iso')
                   'available' -> Space available, in bytes
                   'used' -> Space used, in bytes
                   'active' -> True or False

        """
        dcKey = self._generate_key('o-dc' + datacenterId)
        val = self._cache.get(dcKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self._api()

            datacenter_service = api.system_service().data_centers_service().service(datacenterId)
            d: typing.Any = datacenter_service.get()  # pyright: ignore

            storage = []
            for dd in typing.cast(
                collections.abc.Iterable[typing.Any], datacenter_service.storage_domains_service().list()
            ):  # pyright: ignore
                try:
                    active = dd.status.value
                except Exception:
                    active = 'inactive'

                storage.append(
                    {
                        'id': dd.id,
                        'name': dd.name,
                        'type': dd.type.value,
                        'available': dd.available,
                        'used': dd.used,
                        'active': active == 'active',
                    }
                )

            res: dict[str, typing.Any] = {
                'name': d.name,
                'id': d.id,
                'storage_type': d.local and 'local' or 'shared',
                'description': d.description,
                'storage': storage,
            }

            self._cache.put(dcKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()

    def get_storage_info(
        self, storageId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the datacenter info

        Args:
            datacenterId: Id of the datacenter to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
               'id' -> Storage id
               'name' -> Storage name
               'type' -> Storage type ('data', 'iso')
               'available' -> Space available, in bytes
               'used' -> Space used, in bytes
               # 'active' -> True or False --> This is not provided by api?? (api.storagedomains.get)

        """
        sdKey = self._generate_key('o-sd' + storageId)
        val = self._cache.get(sdKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self._api()

            dd: typing.Any = (
                api.system_service().storage_domains_service().service(storageId).get()
            )  # pyright: ignore

            res = {
                'id': dd.id,
                'name': dd.name,
                'type': dd.type.value,
                'available': dd.available,
                'used': dd.used,
            }

            self._cache.put(sdKey, res, Client.CACHE_TIME_LOW)
            return res
        finally:
            lock.release()

    def create_template(
        self,
        name: str,
        comments: str,
        machine_id: str,
        cluster_id: str,
        storage_id: str,
        display_type: str,
    ) -> str:
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

        try:
            lock.acquire(True)

            api = self._api()

            # cluster = ov.clusters_service().service('00000002-0002-0002-0002-0000000002e4') # .get()
            # vm = ov.vms_service().service('e7ff4e00-b175-4e80-9c1f-e50a5e76d347') # .get()

            vms: typing.Any = api.system_service().vms_service().service(machine_id)

            cluster: typing.Any = (
                api.system_service().clusters_service().service(cluster_id).get()
            )  # pyright: ignore
            vm: typing.Any = vms.get()  # pyright: ignore

            if vm is None:
                raise Exception('Machine not found')

            if cluster is None:
                raise Exception('Cluster not found')

            if vm.status.value != 'down':
                raise Exception('Machine must be powered off to publish it')

            # sd = [ovirt.types.StorageDomain(id=storageId)]
            # dsks = []
            # for dsk in vms.disk_attachments_service().list():
            #    dsks = None
            # dsks.append(params.Disk(id=dsk.get_id(), storage_domains=sd, alias=dsk.get_alias()))
            # dsks.append(dsk)

            tvm = ovirt.types.Vm(id=vm.id)
            tcluster = ovirt.types.Cluster(id=cluster.id)

            template = ovirt.types.Template(name=name, vm=tvm, cluster=tcluster, description=comments)

            # display=display)

            return api.system_service().templates_service().add(template).id  # pyright: ignore
        finally:
            lock.release()

    def get_template_state(self, template_id: str) -> str:
        """
        Returns current template state.
        This method do not uses cache at all (it always tries to get template state from oVirt server)

        Returned values could be:
            ok
            locked
            removed

        (don't know if ovirt returns something more right now, will test what happens when template can't be published)
        """
        try:
            lock.acquire(True)

            api = self._api()

            try:
                template: typing.Any = (
                    api.system_service().templates_service().service(template_id).get()  # pyright: ignore
                )

                if not template:
                    return 'removed'

                return template.status.value
            except Exception:  # Not found
                return 'removed'

        finally:
            lock.release()

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
    ) -> str:
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
        try:
            lock.acquire(True)

            api = self._api()

            logger.debug('Deploying machine %s', name)

            cluster = ovirt.types.Cluster(id=cluster_id)
            template = ovirt.types.Template(id=template_id)

            if self._needs_usb_fix is False and usb_type in (
                'native',
            ):  # Removed 'legacy', from 3.6 is not used anymore, and from 4.0 not available
                usb = ovirt.types.Usb(enabled=True, type=ovirt.types.UsbType.NATIVE)
            else:
                usb = ovirt.types.Usb(enabled=False)

            memoryPolicy = ovirt.types.MemoryPolicy(guaranteed=guaranteed_mb * 1024 * 1024)
            par = ovirt.types.Vm(
                name=name,
                cluster=cluster,
                template=template,
                description=comments,
                type=ovirt.types.VmType.DESKTOP,
                memory=memory_mb * 1024 * 1024,
                memory_policy=memoryPolicy,
                usb=usb,
            )  # display=display,

            return api.system_service().vms_service().add(par).id  # pyright: ignore

        finally:
            lock.release()

    def remove_template(self, templateId: str) -> None:
        """
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        """
        try:
            lock.acquire(True)

            api = self._api()

            api.system_service().templates_service().service(templateId).remove()  # pyright: ignore
            # This returns nothing, if it fails it raises an exception
        finally:
            lock.release()

    def get_machine_state(self, machineId: str) -> str:
        """
        Returns current state of a machine (running, suspended, ...).
        This method do not uses cache at all (it always tries to get machine state from oVirt server)

        Args:
            machineId: Id of the machine to get status

        Returns:
            one of this values:
             unassigned, down, up, powering_up, powered_down,
             paused, migrating_from, migrating_to, unknown, not_responding,
             wait_for_launch, reboot_in_progress, saving_state, restoring_state,
             suspended, image_illegal, image_locked or powering_down
             Also can return'unknown' if Machine is not known
        """
        try:
            lock.acquire(True)

            api = self._api()

            try:
                vm = api.system_service().vms_service().service(machineId).get()  # pyright: ignore

                if vm is None or vm.status is None:  # pyright: ignore
                    return 'unknown'

                return vm.status.value  # pyright: ignore
            except Exception:  # machine not found
                return 'unknown'

        finally:
            lock.release()

    def start_machine(self, machine_id: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self._api()

            vmService: typing.Any = api.system_service().vms_service().service(machine_id)

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.start()

        finally:
            lock.release()

    def stop_machine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self._api()

            vmService: typing.Any = api.system_service().vms_service().service(machineId)

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.stop()

        finally:
            lock.release()

    def suspend_machine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self._api()

            vmService: typing.Any = api.system_service().vms_service().service(machineId)

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.suspend()

        finally:
            lock.release()

    def remove_machine(self, machineId: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self._api()

            vmService: typing.Any = api.system_service().vms_service().service(machineId)

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.remove()

        finally:
            lock.release()

    def update_machine_mac(self, machineid: str, mac: str) -> None:
        """
        Changes the mac address of first nic of the machine to the one specified
        """
        try:
            lock.acquire(True)

            api = self._api()

            vm_service: typing.Any = api.system_service().vms_service().service(machineid)

            if vm_service.get() is None:
                raise Exception('Machine not found')

            nic = vm_service.nics_service().list()[0]  # If has no nic, will raise an exception (IndexError)
            nic.mac.address = mac
            nicService = vm_service.nics_service().service(nic.id)
            nicService.update(nic)
        except IndexError:
            raise Exception('Machine do not have network interfaces!!')

        finally:
            lock.release()

    def fix_usb(self, machineId: str) -> None:
        # Fix for usb support
        if self._needs_usb_fix:
            try:
                lock.acquire(True)

                api = self._api()
                usb = ovirt.types.Usb(enabled=True, type=ovirt.types.UsbType.NATIVE)
                vms: typing.Any = api.system_service().vms_service().service(machineId)
                vmu = ovirt.types.Vm(usb=usb)
                vms.update(vmu)
            finally:
                lock.release()

    def get_console_connection(self, machine_id: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        """
        Gets the connetion info for the specified machine
        """
        try:
            lock.acquire(True)
            api = self._api()

            vm_service: typing.Any = api.system_service().vms_service().service(machine_id)
            vm = vm_service.get()

            if vm is None:
                raise Exception('Machine not found')

            display = vm.display
            ticket = vm_service.ticket()

            # Get host subject
            cert_subject = ''
            if display.certificate is not None:
                cert_subject = display.certificate.subject
            else:
                for i in typing.cast(
                    collections.abc.Iterable[typing.Any], api.system_service().hosts_service().list()
                ):
                    for k in typing.cast(
                        collections.abc.Iterable[typing.Any],
                        api.system_service()
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

            return types.services.ConsoleConnectionInfo(
                type=display.type.value,
                address=display.address,
                port=display.port,
                secure_port=display.secure_port,
                cert_subject=cert_subject,
                ticket=types.services.ConsoleConnectionTicket(value=ticket.value),
            )

        except Exception:
            return None

        finally:
            lock.release()
