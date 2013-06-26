# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from django.utils.translation import ugettext as _
from django.db import IntegrityError 
from uds.models import Provider, Service
from uds.xmlrpc.util.Helpers import dictFromData
from uds.xmlrpc.auths.AdminAuth import needs_credentials
from uds.xmlrpc.util.Exceptions import InsertException, FindException, DeleteException, ValidationException
from uds.core.Environment import Environment
from uds.core import services
import logging

logger = logging.getLogger(__name__)

def infoDictFromServiceInstance(service):
    if service is not None:
        needsPublication = service.publicationType is not None
        maxDeployed = service.maxDeployed
        usesCache = service.usesCache
        usesCache_L2 = service.usesCache_L2
        cacheTooltip =  _(service.cacheTooltip)
        cacheTooltip_L2 = _(service.cacheTooltip_L2)
        needsManager = service.needsManager
        mustAssignManually = service.mustAssignManually
        typeName = service.name()
    else:
        needsPublication = False
        maxDeployed = 0
        usesCache = False
        usesCache_L2 = False
        cacheTooltip =  ''
        cacheTooltip_L2 = ''
        needsManager = False
        mustAssignManually = False
        typeName = ''
        
    
    return { 'needsPublication' : needsPublication, 'maxDeployed' : maxDeployed, 
             'usesCache' : usesCache, 'usesCacheL2' : usesCache_L2, 
             'cacheTooltip' : cacheTooltip, 'cacheTooltipL2' : cacheTooltip_L2, 
             'needsManager' : needsManager, 'mustAssignManually' : mustAssignManually,
             'typeName' : typeName 
        }

def dictFromService(serv):
    service = serv.getInstance()
    return { 'idParent' : str(serv.provider_id),  'id' : str(serv.id), 'name' : serv.name, 
                    'comments' : serv.comments, 'type' : serv.data_type, 'typeName' : _(service.name()), 'info' : infoDictFromServiceInstance(service)
        }

@needs_credentials
def getServices(credentials, idParent):
    '''
    Returns the services providers managed (at database)
    '''
    provider = Provider.objects.get(id=idParent)
    res = []
    for serv in provider.services.order_by('name'):
        try:
            val = dictFromService(serv)
            res.append(val)
        except Exception, e:
            logger.debug(e)
    return res

@needs_credentials
def getAllServices(credentials):
    '''
    Returns all services, don't limited by parent id
    '''
    res = []
    for serv in Service.objects.all().order_by('name'):
        try:
            val = dictFromService(serv)
            val['name'] = serv.provider.name + '\\' + val['name']
            res.append(val)
        except Exception, e:
            logger.debug(e)
    return res

@needs_credentials
def getServiceGui(credentials, idParent, type):
    '''
    Returns the description of an gui for the specified service provider
    '''
    try:
        logger.debug('getServiceGui parameters: {0}, {1}'.format(idParent, type))
        provider = Provider.objects.get(id=idParent).getInstance()
        serviceType = provider.getServiceByType(type)
        service = serviceType( Environment.getTempEnv(), provider)  # Instantiate it so it has the opportunity to alter gui description based on parent
        return service.guiDescription(service)
    except:
        logger.exception('Exception at getServiceGui')
        raise

@needs_credentials
def getService(credentials, id):
    '''
    Returns the specified service provider (at database)
    '''
    logger.debug('getService parameters: {0}'.format(id))
    srv = Service.objects.get(id=id)
    res = [ 
           { 'name' : 'name', 'value' : srv.name },
           { 'name' : 'comments', 'value' : srv.comments },
          ]
    for key, value in srv.getInstance().valuesDict().iteritems():
        valtext = 'value'
        if value.__class__ == list:
            valtext = 'values'
        val = {'name' : key, valtext : value }
        res.append(val)
    return res

@needs_credentials
def createService(credentials, idParent, type, data):
    '''
    Creates a new service with specified type and data associated to the specified parent
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider, getServices, ...
    '''
    provider = Provider.objects.get(id=idParent)
    dic = dictFromData(data)
    try:
        srv = provider.services.create(name = dic['name'], comments = dic['comments'], data_type = type)
        # Invoque serialization with correct environment
        srv.data = srv.getInstance(dic).serialize()
        srv.save()
    except services.Service.ValidationException as e:
        srv.delete()
        raise ValidationException(str(e))
    except IntegrityError: # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dic['name']))
    except Exception as e:
        logger.exception('Unexpected exception')
        raise ValidationException(str(e))
    return True

@needs_credentials
def modifyService(credentials, id, data):
    '''
    Modifies an existing service with specified id and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    try:
        serv = Service.objects.get(pk=id)
        dic = dictFromData(data)
        sp = serv.getInstance(dic)
        serv.data = sp.serialize()
        serv.name = dic['name']
        serv.comments = dic['comments']
        serv.save()
    except services.Service.ValidationException as e:
        raise ValidationException(str(e))
    except IntegrityError: # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dic['name']))
    except Exception as e:
        logger.exception('Unexpected exception')
        raise ValidationException(str(e))
        
    return True

@needs_credentials
def removeService(credentials, id):
    '''
    Removes from database provider with specified id
    '''
    try:
        s = Service.objects.get(id=id)
        if s.deployedServices.count() > 0:
            raise DeleteException(_('Can\'t delete services with deployed services associated'))
        s.delete()
    except Service.DoesNotExist:
        raise FindException(_('Can\'t locate the service') + '.' + _('Please, refresh interface'))
    return True



# Registers XML RPC Methods
def registerServiceFunctions(dispatcher):
    dispatcher.register_function(getServices, 'getServices')
    dispatcher.register_function(getAllServices, 'getAllServices')
    dispatcher.register_function(getServiceGui, 'getServiceGui')
    dispatcher.register_function(getService, 'getService')
    dispatcher.register_function(createService, 'createService')
    dispatcher.register_function(modifyService, 'modifyService')
    dispatcher.register_function(removeService, 'removeService')
