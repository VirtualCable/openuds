'''
Created on Nov 15, 2012

@author: dkmaster
'''

from django.utils.translation import ugettext as _
import logging

logger = logging.getLogger(__name__)

class oVirtHelpers(object):
    
    @staticmethod
    def getResources(parameters):
        '''
        This helper is designed as a callback for machine selector, so we can provide valid clusters and datastores domains based on it
        '''
        from OVirtProvider import Provider
        from uds.core.Environment import Environment
        logger.debug('Parameters received by getResources Helper: {0}'.format(parameters))
        env = Environment(parameters['ev'])
        provider = Provider(env)
        provider.unserialize(parameters['ov'])
        
        # Obtains datacenter from cluster
        ci = provider.getClusterInfo(parameters['cluster'])

        res = []        
        # Get storages for that datacenter
        for storage in provider.getDatacenterInfo(ci['datacenter_id'])['storage']:
            if storage['type'] == 'data':
                space, free = storage['available']/1024/1024/1024, (storage['available']-storage['used'])/1024/1024/1024
                
                res.append( {'id': storage['id'], 'text': "%s (%4.2f Gb/%4.2f Gb) %s" % (storage['name'], space, free, storage['active'] and '(ok)' or '(disabled)' ) }) 
        data = [{
                'name' : 'datastore', 'values' : res
        }]
        
        logger.debug('return data: {0}'.format(data))
        return data
                
        
    
