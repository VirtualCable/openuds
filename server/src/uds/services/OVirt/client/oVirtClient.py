'''
Created on Nov 14, 2012

@author: dkmaster
'''

from ovirtsdk.xml import params
from ovirtsdk.api import API

import threading
import logging
import re

__updated__ = '2015-09-21'

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
                cached_api.disconnect()
            except:
                # Nothing happens, may it was already disconnected
                pass
        try:
            cached_api_key = aKey
            cached_api = API(url='https://' + self._host + '/api', username=self._username, password=self._password, timeout=self._timeout, insecure=True, debug=False)
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

    def _isFullyFunctionalVersion(self, api):
        '''
        Same as isFullyFunctionalVersion, but without locking. For internal use only
        '''
        version = re.search('([0-9]+).([0-9]+).([0-9]+)?', api.get_product_info().full_version).groups()
        if version[0] == '3' and version[1] == '5' and (version[2] is None or version[2] < '4'):  # 3.5 fails if disks are in request
            return [False, 'Version 3.5 is not fully supported due a BUG in oVirt REST API (but partially supported. See UDS Documentation)']

        return [True, 'Test successfully passed']


    def isFullyFunctionalVersion(self):
        try:
            lock.acquire(True)
            return self._isFullyFunctionalVersion(self.__getApi())
        finally:
            lock.release()

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

            vms = api.vms.list(query='name!=UDS*')

            logger.debug('oVirt VMS: {}'.format(vms))

            res = []

            for vm in vms:
                res.append({'name': vm.get_name(), 'id': vm.get_id(), 'cluster_id': vm.get_cluster().get_id()})

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

            clusters = api.clusters.list()

            res = []

            for cluster in clusters:
                dc = cluster.get_data_center()

                if dc is not None:
                    dc = dc.get_id()

                val = {'name': cluster.get_name(), 'id': cluster.get_id(), 'datacenter_id': dc}

                # Updates cache info for every single cluster
                clKey = self.__getKey('o-cluster' + cluster.get_id())
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

            c = api.clusters.get(id=clusterId)

            dc = c.get_data_center()

            if dc is not None:
                dc = dc.get_id()

            res = {'name': c.get_name(), 'id': c.get_id(), 'datacenter_id': dc}
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

            d = api.datacenters.get(id=datacenterId)
            storage = []
            for dd in d.storagedomains.list():
                try:
                    active = dd.get_status().get_state()
                except:
                    active = 'inactive'

                storage.append({'id': dd.get_id(), 'name': dd.get_name(), 'type': dd.get_type(),
                                'available': dd.get_available(), 'used': dd.get_used(),
                                'active': active == 'active'})

            res = {'name': d.get_name(), 'id': d.get_id(), 'storage_type': d.get_storage_type(),
                    'storage_format': d.get_storage_format(), 'description': d.get_description(),
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

            dd = api.storagedomains.get(id=storageId)

            res = {
                'id': dd.get_id(),
                'name': dd.get_name(),
                'type': dd.get_type(),
                'available': dd.get_available(), 'used': dd.get_used()
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

            cluster = api.clusters.get(id=clusterId)
            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            if cluster is None:
                raise Exception('Cluster not found')

            if vm.get_status().get_state() != 'down':
                raise Exception('Machine must be in down state to publish it')

            print(vm.disks.list())

            # Create disks description to be created in specified storage domain, one for each disk
            sd = params.StorageDomains(storage_domain=[params.StorageDomain(id=storageId)])

            fix = not self._isFullyFunctionalVersion(api)[0]  # If we need a fix for "publish"

            print "FIX: {}".format(fix)

            dsks = []
            for dsk in vm.disks.list():
                dsks.append(params.Disk(id=dsk.get_id(), storage_domains=sd, alias=dsk.get_alias()))
                # dsks.append(dsk)

            disks = params.Disks(disk=dsks)

            # Create display description
            # display = params.Display(type_=displayType)

            # TODO: Restore proper template creation mechanism
            if fix is True:
                vm = params.VM(id=vm.get_id())
            else:
                vm = params.VM(id=vm.get_id(), disks=disks)

            template = params.Template(
                name=name,
                vm=vm,
                cluster=params.Cluster(id=cluster.get_id()),
                description=comments
            )

            # display=display)

            return api.templates.add(template).get_id()
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

            template = api.templates.get(id=templateId)

            if template is None:
                return 'removed'

            return template.get_status().get_state()

        finally:
            lock.release()

    def deployFromTemplate(self, name, comments, templateId, clusterId, displayType, memoryMB, guaranteedMB):
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
        logger.debug('Deploying machine with name "{0}" from template {1} at cluster {2} with display {3}, memory {4} and guaranteed {5}'.format(
            name, templateId, clusterId, displayType, memoryMB, guaranteedMB))
        try:
            lock.acquire(True)

            api = self.__getApi()

            logger.debug('Deploying machine {0}'.format(name))

            cluster = params.Cluster(id=clusterId)
            template = params.Template(id=templateId)
            display = params.Display(type_=displayType)

            memoryPolicy = params.MemoryPolicy(guaranteed=guaranteedMB * 1024 * 1024)
            par = params.VM(name=name, cluster=cluster, template=template, description=comments,
                            type_='desktop', memory=memoryMB * 1024 * 1024, memory_policy=memoryPolicy)  # display=display,

            return api.vms.add(par).get_id()

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

            template = api.templates.get(id=templateId)
            if template is None:
                raise Exception('Template does not exists')

            template.delete()
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

            vm = api.vms.get(id=machineId)

            if vm is None or vm.get_status() is None:
                return 'unknown'

            return vm.get_status().get_state()

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

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            vm.start()

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

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            vm.stop()

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

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            vm.suspend()

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

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            vm.delete()

        finally:
            lock.release()

    def updateMachineMac(self, machineId, macAddres):
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        try:
            lock.acquire(True)

            api = self.__getApi()

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            nic = vm.nics.list()[0]  # If has no nic, will raise an exception (IndexError)

            nic.get_mac().set_address(macAddres)

            nic.update()  # Updates the nic

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

            vm = api.vms.get(id=machineId)

            if vm is None:
                raise Exception('Machine not found')

            display = vm.get_display()
            ticket = vm.ticket().get_ticket()
            return {
                'type': display.get_type(),
                'address': display.get_address(),
                'port': display.get_port(),
                'secure_port': display.get_secure_port(),
                'monitors': display.get_monitors(),
                'cert_subject': display.get_certificate().get_subject(),
                'ticket': {
                    'value': ticket.get_value(),
                    'expiry': ticket.get_expiry()
                }
            }

        finally:
            lock.release()

    def desktopLogin(self, machineId, username, password, domain):
        pass
