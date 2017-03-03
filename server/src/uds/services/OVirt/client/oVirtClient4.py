'''
Created on Nov 14, 2012

@author: dkmaster
'''

import ovirtsdk4 as ovirt

import threading
import logging
import six

__updated__ = '2017-03-03'

logger = logging.getLogger(__name__)

lock = threading.Lock()

cached_api = None
cached_api_key = None


class Client(object):
    '''
    Module to manage oVirt connections using ovirtsdk.

    Due to the fact that we can't create two proxy connections at same time, we serialize all access to ovirt platform.
    Only one request and one live connection can exists at a time.

    This can waste a lot of time, so use of cache here is more than important to achieve aceptable performance.

    '''

    CACHE_TIME_LOW = 60 * 5  # Cache time for requests are 5 minutes by default
    CACHE_TIME_HIGH = 60 * 30  # Cache time for requests that are less probable to change (as cluster perteinance of a machine)

    def __getKey(self, prefix=''):
        '''
        Creates a key for the cache, using the prefix indicated as part of it

        Returns:
            The cache key, taking into consideration the prefix
        '''
        return prefix + self._host + self._username + self._password + str(self._timeout)

    def __getApi(self):
        '''
        Gets the api connection.

        Again, due to the fact that ovirtsdk don't allow (at this moment, but it's on the "TODO" list) concurrent access to
        more than one server, we keep only one opened connection.

        Must be accesed "locked", so we can safely alter cached_api and cached_api_key
        '''
        global cached_api, cached_api_key
        aKey = self.__getKey('o-host')
        # if cached_api_key == aKey:
        #    return cached_api

        if cached_api is not None:
            try:
                cached_api.close()
            except:
                # Nothing happens, may it was already disconnected
                pass
        try:
            cached_api_key = aKey
            cached_api = ovirt.Connection(url='https://' + self._host + '/ovirt-engine/api', username=self._username, password=self._password, timeout=self._timeout, insecure=True, debug=True)
            return cached_api
        except:
            logger.exception('Exception connection ovirt at {0}'.format(self._host))
            cached_api_key = None
            raise Exception("Can't connet to server at {0}".format(self._host))
            return None

    def __init__(self, host, username, password, timeout, cache):
        self._host = host
        self._username = username
        self._password = password
        self._timeout = int(timeout)
        self._cache = cache

    def test(self):
        try:
            lock.acquire(True)
            return self.__getApi().test()
        except Exception as e:
            logger.error('Testing Server failed: {0}'.format(e))
            return False
        finally:
            lock.release()


    def isFullyFunctionalVersion(self):
        '''
        '4.0 version is always functional (right now...)
        '''
        return [True, 'Test successfully passed']

    def getVms(self, force=False):
        '''
        Obtains the list of machines inside ovirt that do aren't part of uds

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'cluster_id'

        '''
        vmsKey = self.__getKey('o-vms')
        val = self._cache.get(vmsKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            vms = api.system_service().vms_service().list()

            logger.debug('oVirt VMS: {}'.format(vms))

            res = []

            for vm in vms:
                try:
                    pair = [vm.usb.enabled, vm.usb.type.value]
                except:
                    pair = [False, '']
                res.append({'name': vm.name, 'id': vm.id, 'cluster_id': vm.cluster.id, 'usb': pair })

            self._cache.put(vmsKey, res, Client.CACHE_TIME_LOW)

            return res

        finally:
            lock.release()

    def getClusters(self, force=False):
        '''
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

        '''
        clsKey = self.__getKey('o-clusters')
        val = self._cache.get(clsKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            clusters = api.system_service().clusters_service().list()

            res = []

            for cluster in clusters:
                dc = cluster.data_center

                if dc is not None:
                    dc = dc.id

                val = {'name': cluster.name, 'id': cluster.id, 'datacenter_id': dc}

                # Updates cache info for every single cluster
                clKey = self.__getKey('o-cluster' + cluster.id)
                self._cache.put(clKey, val)

                if dc is not None:
                    res.append(val)

            self._cache.put(clsKey, res, Client.CACHE_TIME_HIGH)

            return res

        finally:
            lock.release()

    def getClusterInfo(self, clusterId, force=False):
        '''
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
        '''
        clKey = self.__getKey('o-cluster' + clusterId)
        val = self._cache.get(clKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            c = api.system_service().clusters_service().service(six.binary_type(clusterId)).get()

            dc = c.data_center

            if dc is not None:
                dc = dc.id

            res = {'name': c.name, 'id': c.id, 'datacenter_id': dc}
            self._cache.put(clKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()

    def getDatacenterInfo(self, datacenterId, force=False):
        '''
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
                'storage_format' -> ('v1', v2')
                'description'
                'storage' -> array of dictionaries, with:
                   'id' -> Storage id
                   'name' -> Storage name
                   'type' -> Storage type ('data', 'iso')
                   'available' -> Space available, in bytes
                   'used' -> Space used, in bytes
                   'active' -> True or False

        '''
        dcKey = self.__getKey('o-dc' + datacenterId)
        val = self._cache.get(dcKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            datacenter_service = api.system_service().data_centers_service().service(six.binary_type(datacenterId))
            d = datacenter_service.get()

            storage = []
            for dd in datacenter_service.storage_domains_service().list():
                try:
                    active = dd.status.value
                except:
                    active = 'inactive'

                storage.append({'id': dd.id, 'name': dd.name, 'type': dd.type.value,
                                'available': dd.available, 'used': dd.used,
                                'active': active == 'active'})

            res = {'name': d.name, 'id': d.id, 'storage_type': d.local and 'local' or 'shared',
                    'storage_format': d.storage_format.value, 'description': d.description,
                    'storage': storage}

            self._cache.put(dcKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()

    def getStorageInfo(self, storageId, force=False):
        '''
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

        '''
        sdKey = self.__getKey('o-sd' + storageId)
        val = self._cache.get(sdKey)

        if val is not None and force is False:
            return val

        try:
            lock.acquire(True)

            api = self.__getApi()

            dd = api.system_service().storage_domains_service().service(six.binary_type(storageId)).get()

            res = {
                'id': dd.id,
                'name': dd.name,
                'type': dd.type.value,
                'available': dd.available,
                'used': dd.used
            }

            self._cache.put(sdKey, res, Client.CACHE_TIME_LOW)
            return res
        finally:
            lock.release()

    def makeTemplate(self, name, comments, machineId, clusterId, storageId, displayType):
        '''
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
        '''
        logger.debug("n: {0}, c: {1}, vm: {2}, cl: {3}, st: {4}, dt: {5}".format(name, comments, machineId, clusterId, storageId, displayType))

        try:
            lock.acquire(True)

            api = self.__getApi()

            # cluster = ov.clusters_service().service('00000002-0002-0002-0002-0000000002e4') # .get()
            # vm = ov.vms_service().service('e7ff4e00-b175-4e80-9c1f-e50a5e76d347') # .get()

            vms = api.system_service().vms_service().service(six.binary_type(machineId))

            cluster = api.system_service().clusters_service().service(six.binary_type(clusterId)).get()
            vm = vms.get()

            if vm is None:
                raise Exception('Machine not found')

            if cluster is None:
                raise Exception('Cluster not found')

            if vm.status.value != 'down':
                raise Exception('Machine must be in down state to publish it')

            # sd = [ovirt.types.StorageDomain(id=storageId)]
            # dsks = []
            # for dsk in vms.disk_attachments_service().list():
            #    dsks = None
                # dsks.append(params.Disk(id=dsk.get_id(), storage_domains=sd, alias=dsk.get_alias()))
                # dsks.append(dsk)

            tvm = ovirt.types.Vm(id=vm.id)
            tcluster = ovirt.types.Cluster(id=cluster.id)

            template = ovirt.types.Template(
                name=name,
                vm=tvm,
                cluster=tcluster,
                description=comments
            )

            # display=display)

            return api.system_service().templates_service().add(template).id
        finally:
            lock.release()

    def getTemplateState(self, templateId):
        '''
        Returns current template state.
        This method do not uses cache at all (it always tries to get template state from oVirt server)

        Returned values could be:
            ok
            locked
            removed

        (don't know if ovirt returns something more right now, will test what happens when template can't be published)
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            template = api.system_service().templates_service().service(six.binary_type(templateId)).get()

            if template is None:
                return 'removed'

            return template.status.value

        finally:
            lock.release()

    def deployFromTemplate(self, name, comments, templateId, clusterId, displayType, usbType, memoryMB, guaranteedMB):
        '''
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
        '''
        logger.debug('Deploying machine with name "{0}" from template {1} at cluster {2} with display {3} and usb {4}, memory {5} and guaranteed {6}'.format(
            name, templateId, clusterId, displayType, usbType, memoryMB, guaranteedMB))
        try:
            lock.acquire(True)

            api = self.__getApi()

            logger.debug('Deploying machine {0}'.format(name))

            cluster = ovirt.types.Cluster(id=six.binary_type(clusterId))
            template = ovirt.types.Template(id=six.binary_type(templateId))
            if usbType in ('native', 'legacy'):
                usb = ovirt.types.Usb(enabled=True, type=ovirt.types.UsbType.NATIVE if usbType == 'native' else ovirt.types.UsbType.LEGACY)
            else:
                usb = ovirt.types.Usb(enabled=False)

            memoryPolicy = ovirt.types.MemoryPolicy(guaranteed=guaranteedMB * 1024 * 1024)
            par = ovirt.types.Vm(name=name, cluster=cluster, template=template, description=comments,
                            type=ovirt.types.VmType.DESKTOP, memory=memoryMB * 1024 * 1024, memory_policy=memoryPolicy,
                            usb=usb)  # display=display,

            return api.system_service().vms_service().add(par).id

        finally:
            lock.release()

    def removeTemplate(self, templateId):
        '''
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            api.system_service().templates_service().service(six.binary_type(templateId)).remove()
            # This returns nothing, if it fails it raises an exception
        finally:
            lock.release()

    def getMachineState(self, machineId):
        '''
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
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vm = api.system_service().vms_service().service(six.binary_type(machineId)).get()

            if vm is None or vm.status is None:
                return 'unknown'

            return vm.status.value

        finally:
            lock.release()

    def startMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()


            vmService = api.system_service().vms_service().service(six.binary_type(machineId))

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.start()

        finally:
            lock.release()

    def stopMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService = api.system_service().vms_service().service(six.binary_type(machineId))

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.stop()

        finally:
            lock.release()

    def suspendMachine(self, machineId):
        '''
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService = api.system_service().vms_service().service(six.binary_type(machineId))

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.suspend()

        finally:
            lock.release()

    def removeMachine(self, machineId):
        '''
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService = api.system_service().vms_service().service(six.binary_type(machineId))

            if vmService.get() is None:
                raise Exception('Machine not found')

            vmService.remove()

        finally:
            lock.release()

    def updateMachineMac(self, machineId, macAddres):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vmService = api.system_service().vms_service().service(six.binary_type(machineId))

            if vmService.get() is None:
                raise Exception('Machine not found')

            nic = vmService.nics_service().list()[0]  # If has no nic, will raise an exception (IndexError)
            nic.mac.address = macAddres
            nicService = vmService.nics_service().service(nic.id)
            nicService.update(nic)
        except IndexError:
            raise Exception('Machine do not have network interfaces!!')

        finally:
            lock.release()

    def getConsoleConnection(self, machineId):
        '''
        Gets the connetion info for the specified machine
        '''
        try:
            lock.acquire(True)
            api = self.__getApi()

            vmService = api.system_service().vms_service().service(six.binary_type(machineId))
            vm = vmService.get()

            if vm is None:
                raise Exception('Machine not found')

            display = vm.display
            ticket = vmService.ticket()

            # Get host subject
            cert_subject = ''
            if display.certificate != None:
                cert_subject = display.certificate.subject
            else:
                for i in api.system_service().hosts_service().list():
                    for k in api.system_service().hosts_service().service(i.id).nics_service().list():
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
                'ticket': {
                    'value': ticket.value,
                    'expiry': ticket.expiry
                }
            }

        finally:
            lock.release()

    def desktopLogin(self, machineId, username, password, domain):
        pass
