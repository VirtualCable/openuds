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
import threading
import logging
import typing
import collections.abc

import ovirtsdk4 as ovirt

# Sometimes, we import ovirtsdk4 but "types" does not get imported... event can't be found????
# With this seems to work propertly
try:
    from ovirtsdk4 import types as ovirtTypes
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
    _needsUsbFix = True

    def __getKey(self, prefix: str = '') -> str:
        """
        Creates a key for the cache, using the prefix indicated as part of it

        Returns:
            The cache key, taking into consideration the prefix
        """
        return "{}{}{}{}{}".format(
            prefix, self._host, self._username, self._password, self._timeout
        )

    def __getApi(self) -> ovirt.Connection:
        """
        Gets the api connection.

        Again, due to the fact that ovirtsdk don't allow (at this moment, but it's on the "TODO" list) concurrent access to
        more than one server, we keep only one opened connection.

        Must be accesed "locked", so we can safely alter cached_api and cached_api_key
        """
        aKey = self.__getKey('o-host')
        # if cached_api_key == aKey:
        #    return cached_api

        if Client.cached_api:
            try:
                Client.cached_api.close()
            except Exception:  # nosec: this is a "best effort" close
                # Nothing happens, may it was already disconnected
                pass
        try:
            Client.cached_api_key = aKey
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
        self._needsUsbFix = True

    def test(self) -> bool:
        try:
            lock.acquire(True)
            return self.__getApi().test()
        except Exception as e:
            logger.error('Testing Server failed for oVirt: %s', e)
            return False
        finally:
            lock.release()

    def isFullyFunctionalVersion(self) -> typing.Tuple[bool, str]:
        """
        '4.0 version is always functional (right now...)
        """
        return True, 'Test successfully passed'

    def getVms(
        self, force: bool = False
    ) -> list[collections.abc.MutableMapping[str, typing.Any]]:
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
        vmsKey = self.__getKey('o-vms')
        val: typing.Optional[typing.Any] = self._cache.get(vmsKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            vms: typing.Iterable[typing.Any] = api.system_service().vms_service().list()  # type: ignore

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

    def getClusters(
        self, force: bool = False
    ) -> list[collections.abc.MutableMapping[str, typing.Any]]:
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
        clsKey = self.__getKey('o-clusters')
        val: typing.Optional[typing.Any] = self._cache.get(clsKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            clusters: list[typing.Any] = api.system_service().clusters_service().list()  # type: ignore

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
                clKey = self.__getKey('o-cluster' + cluster.id)
                self._cache.put(clKey, val)

                if dc is not None:
                    res.append(val)

            self._cache.put(clsKey, res, Client.CACHE_TIME_HIGH)

            return res

        finally:
            lock.release()

    def getClusterInfo(
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
        clKey = self.__getKey('o-cluster' + clusterId)
        val = self._cache.get(clKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            c: typing.Any = api.system_service().clusters_service().service(clusterId).get()  # type: ignore

            dc = c.data_center

            if dc is not None:
                dc = dc.id

            res = {'name': c.name, 'id': c.id, 'datacenter_id': dc}
            self._cache.put(clKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()

    def getDatacenterInfo(
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
        dcKey = self.__getKey('o-dc' + datacenterId)
        val = self._cache.get(dcKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            datacenter_service = (
                api.system_service().data_centers_service().service(datacenterId)
            )
            d: typing.Any = datacenter_service.get()  # type: ignore

            storage = []
            for dd in typing.cast(typing.Iterable, datacenter_service.storage_domains_service().list()):  # type: ignore
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

            res = {
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

    def getStorageInfo(
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
        sdKey = self.__getKey('o-sd' + storageId)
        val = self._cache.get(sdKey)

        if val and not force:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            dd: typing.Any = api.system_service().storage_domains_service().service(storageId).get()  # type: ignore

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

    def makeTemplate(
        self,
        name: str,
        comments: str,
        machineId: str,
        clusterId: str,
        storageId: str,
        displayType: str,
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
            machineId,
            clusterId,
            storageId,
            displayType,
        )

        try:
            lock.acquire(True)

            api = self.__getApi()

            # cluster = ov.clusters_service().service('00000002-0002-0002-0002-0000000002e4') # .get()
            # vm = ov.vms_service().service('e7ff4e00-b175-4e80-9c1f-e50a5e76d347') # .get()

            vms = api.system_service().vms_service().service(machineId)

            cluster: typing.Any = api.system_service().clusters_service().service(clusterId).get()  # type: ignore
            vm: typing.Any = vms.get()  # type: ignore

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

            template = ovirt.types.Template(
                name=name, vm=tvm, cluster=tcluster, description=comments
            )

            # display=display)

            return api.system_service().templates_service().add(template).id  # type: ignore
        finally:
            lock.release()

    def getTemplateState(self, templateId: str) -> str:
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

            api = self.__getApi()

            try:
                template: typing.Any = (
                    api.system_service().templates_service().service(templateId).get()  # type: ignore
                )

                if not template:
                    return 'removed'

                return template.status.value
            except Exception:  # Not found
                return 'removed'

        finally:
            lock.release()

    def deployFromTemplate(
        self,
        name: str,
        comments: str,
        templateId: str,
        clusterId: str,
        displayType: str,
        usbType: str,
        memoryMB: int,
        guaranteedMB: int,
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
            templateId,
            clusterId,
            displayType,
            usbType,
            memoryMB,
            guaranteedMB,
        )
        try:
            lock.acquire(True)

            api = self.__getApi()

            logger.debug('Deploying machine %s', name)

            cluster = ovirt.types.Cluster(id=clusterId)
            template = ovirt.types.Template(id=templateId)

            if self._needsUsbFix is False and usbType in (
                'native',
            ):  # Removed 'legacy', from 3.6 is not used anymore, and from 4.0 not available
                usb = ovirt.types.Usb(enabled=True, type=ovirt.types.UsbType.NATIVE)
            else:
                usb = ovirt.types.Usb(enabled=False)

            memoryPolicy = ovirt.types.MemoryPolicy(
                guaranteed=guaranteedMB * 1024 * 1024
            )
            par = ovirt.types.Vm(
                name=name,
                cluster=cluster,
                template=template,
                description=comments,
                type=ovirt.types.VmType.DESKTOP,
                memory=memoryMB * 1024 * 1024,
                memory_policy=memoryPolicy,
                usb=usb,
            )  # display=display,

            return api.system_service().vms_service().add(par).id  # type: ignore

        finally:
            lock.release()

    def removeTemplate(self, templateId: str) -> None:
        """
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            api.system_service().templates_service().service(templateId).remove()  # type: ignore
            # This returns nothing, if it fails it raises an exception
        finally:
            lock.release()

    def getMachineState(self, machineId: str) -> str:
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

            api = self.__getApi()

            try:
                vm = api.system_service().vms_service().service(machineId).get()  # type: ignore

                if vm is None or vm.status is None:  # type: ignore
                    return 'unknown'

                return vm.status.value  # type: ignore
            except Exception:  # machine not found
                return 'unknown'

        finally:
            lock.release()

    def startMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.start()

        finally:
            lock.release()

    def stopMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.stop()

        finally:
            lock.release()

    def suspendMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.suspend()

        finally:
            lock.release()

    def removeMachine(self, machineId: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.remove()

        finally:
            lock.release()

    def updateMachineMac(self, machineId: str, macAddres: str) -> None:
        """
        Changes the mac address of first nic of the machine to the one specified
        """
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )

            if vmService.get() is None:
                raise Exception('Machine not found')

            nic = vmService.nics_service().list()[
                0
            ]  # If has no nic, will raise an exception (IndexError)
            nic.mac.address = macAddres
            nicService = vmService.nics_service().service(nic.id)
            nicService.update(nic)
        except IndexError:
            raise Exception('Machine do not have network interfaces!!')

        finally:
            lock.release()

    def fixUsb(self, machineId: str) -> None:
        # Fix for usb support
        if self._needsUsbFix:
            try:
                lock.acquire(True)

                api = self.__getApi()
                usb = ovirt.types.Usb(enabled=True, type=ovirt.types.UsbType.NATIVE)
                vms: typing.Any = api.system_service().vms_service().service(machineId)
                vmu = ovirt.types.Vm(usb=usb)
                vms.update(vmu)
            finally:
                lock.release()

    def getConsoleConnection(
        self, machineId: str
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        """
        Gets the connetion info for the specified machine
        """
        try:
            lock.acquire(True)
            api = self.__getApi()

            vmService: typing.Any = (
                api.system_service().vms_service().service(machineId)
            )
            vm = vmService.get()

            if vm is None:
                raise Exception('Machine not found')

            display = vm.display
            ticket = vmService.ticket()

            # Get host subject
            cert_subject = ''
            if display.certificate is not None:
                cert_subject = display.certificate.subject
            else:
                for i in typing.cast(
                    typing.Iterable, api.system_service().hosts_service().list()
                ):
                    for k in typing.cast(
                        typing.Iterable,
                        api.system_service()
                        .hosts_service()
                        .service(i.id)
                        .nics_service()  # type: ignore
                        .list(),
                    ):
                        if k.ip.address == display.address:
                            cert_subject = i.certificate.subject
                            break
                    # If found
                    if cert_subject != '':
                        break

            return {
                'type': display.type.value,
                'address': display.address,
                'port': display.port,
                'secure_port': display.secure_port,
                'monitors': display.monitors,
                'cert_subject': cert_subject,
                'ticket': {'value': ticket.value, 'expiry': ticket.expiry},
            }

        except Exception:
            return None

        finally:
            lock.release()
