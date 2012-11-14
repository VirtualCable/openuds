'''
Created on Nov 14, 2012

@author: dkmaster
'''

from ovirtsdk.xml import params
from ovirtsdk.api import API

import threading
import logging

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

    CACHE_TIME_LOW = 60*5 # Cache time for requests are 5 minutes by default
    CACHE_TIME_HIGH = 60*30 # Cache time for requests that are less probable to change (as cluster perteinance of a machine)

    def __getKey(self, prefix = ''):
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
        
        Must be acceses "locked", we can alter cached_api and cached_api_key
        '''
        global cached_api, cached_api_key 
        aKey = self.__getKey('o-host')
        if cached_api_key == aKey:
            return cached_api
        
        if cached_api is not None:
            try:
                cached_api.disconnect()
            except:
                # Nothing happens, may it was already disconnected
                pass
        
        cached_api_key = aKey
        cached_api = API(url='https://'+self._host, username=self._username, password=self._password, timeout=self._timeout, insecure=True, debug=False)
        return cached_api

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
            print e
            return False
        finally:
            lock.release()
            
    def getVms(self, force = False):
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
            
            res = []
            
            for vm in vms:
                res.append({ 'name' : vm.get_name(), 'id' : vm.get_id(), 'cluster_id' : vm.get_cluster().get_id() })
                
            self._cache.put(vmsKey, res, Client.CACHE_TIME_LOW)
            
            return res
        
        finally:
            lock.release()
            
    def getClusterInfo(self, clusterId, force = False):
        '''
        Obtains the cluster info

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.
            
        Returns
        
            A dictionary with following values
                'name'
                'id'
                'description'
                'datacenter_id'
        '''
        clKey = self.__getKey('o-cluster'+clusterId)
        val = self._cache.get(clKey)
        
        if val is not None and force is False:
            return val
        
        try:
            lock.acquire(True)
            
            api = self.__getApi()
            
            c = api.clusters.get(id=clusterId)
            
            res = { 'name' : c.get_name(), 'id' : c.get_id(), 'datacenter_id' : c.get_data_center().get_id() }
            self._cache.put(clKey, res, Client.CACHE_TIME_HIGH)
            return res
        finally:
            lock.release()
        
    def getDatacenterInfo(self, datacenterId, force = False):
        '''
        Obtains the cluster info

        Args:
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
        dcKey = self.__getKey('o-dc'+datacenterId)
        val = self._cache.get(dcKey)
        
        if val is not None and force is False:
            return val
        
        try:
            lock.acquire(True)
            
            api = self.__getApi()
            
            d = api.datacenters.get(id=datacenterId)
            storage = []
            for dd in d.storagedomains.list():
                storage.append( { 'id' : dd.get_id(), 'name' : dd.get_name(), 'type' : dd.get_type(), 
                                  'available' : dd.get_available(), 'used' : dd.get_used(), 
                                  'active' : dd.get_status().get_state() == 'active' } )
            
            
            res = { 'name' : d.get_name(), 'id' : d.get_id(), 'storage_type' : d.get_storage_type(), 
                    'storage_format' : d.get_storage_format(), 'description' : d.get_description(),
                    'storage' : storage }
            
            self._cache.put(dcKey, res, Client.CACHE_TIME_HIGH)
            return res
        except Exception as e:
            print e
        finally:
            lock.release()

