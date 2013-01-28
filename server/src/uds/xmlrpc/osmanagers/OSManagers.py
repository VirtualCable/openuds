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
from uds.models import OSManager
from uds.core.osmanagers.OSManagersFactory import OSManagersFactory
from ..util.Exceptions import DeleteException, FindException, ValidationException, InsertException, ModifyException
from ..util.Helpers import dictFromData
from ..auths.AdminAuth import needs_credentials
from uds.core.Environment import Environment
from uds.core import osmanagers

import logging

logger = logging.getLogger(__name__)

@needs_credentials
def getOSManagersTypes(credentials):
    '''
    Returns the types of services providers registered in system
    '''
    res = []
    for type in OSManagersFactory.factory().providers().values():
        val = { 'name' : type.name(), 'type' : type.type(), 'description' : type.description(), 'icon' : type.icon() }
        res.append(val)
    return res

@needs_credentials
def getOSManagers(credentials):
    '''
    Returns the services providers managed (at database)
    '''
    res = []
    for prov in OSManager.objects.order_by('name'):
        try:
            val = { 'id' : str(prov.id), 'name' : prov.name, 'comments' : prov.comments, 'type' : prov.data_type, 'typeName' : prov.getInstance().name() }
            res.append(val)
        except Exception:
            pass
    return res

@needs_credentials
def getOSManagerGui(credentials, type):
    '''
    Returns the description of an gui for the specified service provider
    '''
    spType = OSManagersFactory.factory().lookup(type)
    return spType.guiDescription()

@needs_credentials
def getOSManager(credentials, id):
    '''
    Returns the specified service provider (at database)
    '''
    data = OSManager.objects.get(pk=id)
    res = [ 
           { 'name' : 'name', 'value' : data.name },
           { 'name' : 'comments', 'value' : data.comments },
          ]
    for key, value in data.getInstance().valuesDict().iteritems():
        valtext = 'value'
        if value.__class__ == list:
            valtext = 'values'
        val = {'name' : key, valtext : value }
        res.append(val)
    return res

@needs_credentials
def createOSManager(credentials, type, data):
    '''
    Creates a new service provider with specified type and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    dict = dictFromData(data)
    try:
        # First create data without serialization, then serialies data with correct environment
        sp = OSManager.objects.create(name = dict['name'], comments = dict['comments'], data_type = type)
        sp.data = sp.getInstance(dict).serialize()
        sp.save()
    except osmanagers.OSManager.ValidationException, e:
        sp.delete()
        raise ValidationException(str(e))
    except IntegrityError: # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dict['name']))
    return True

@needs_credentials
def modifyOSManager(credentials, id, data):
    '''
    Modifies an existing service provider with specified id and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    osm = OSManager.objects.get(pk=id)
    dps = osm.deployedServices.all().count()
    if dps > 0:
        errorDps =  ','.join([ o.name for o in osm.deployedServices.all()])
        raise ModifyException(_('This os mnager is being used by deployed services') + ' ' + errorDps)
    dict = dictFromData(data)
    sp = osm.getInstance(dict)
    osm.data = sp.serialize()
    osm.name = dict['name']
    osm.comments = dict['comments']
    osm.save()
    return True
    
@needs_credentials
def removeOSManager(credentials, id):
    '''
    Removes from os manager with specified id
    '''
    try:
        if OSManager.objects.get(pk=id).remove() == False:
            raise DeleteException(_('There is deployed services using this os manager'))
    except OSManager.DoesNotExist:
        raise FindException(_('Can\'t find os manager'))
    
    return True

@needs_credentials
def testOsManager(credentials, type, data):
    '''
    invokes the test function of the specified service provider type, with the suplied data
    '''
    logger.debug("Testing service provider, type: {0}, data:{1}".format(type, data))
    spType = OSManagersFactory.factory().lookup(type)
    # We need an "temporary" environment to test this service
    dict = dictFromData(data)
    res = spType.test(Environment.getTempEnv(), dict)
    return {'ok' : res[0], 'message' : res[1]}

@needs_credentials
def checkOSManager(credentials, id):
    '''
    Invokes the check function of the specified service provider
    '''
    prov = OSManager.objects.get(id=id)
    sp = prov.getInstance()
    return sp.check()
    

# Registers XML RPC Methods
def registerOSManagersFunctions(dispatcher):
    dispatcher.register_function(getOSManagersTypes, 'getOSManagersTypes')
    dispatcher.register_function(getOSManagers, 'getOSManagers')
    dispatcher.register_function(getOSManagerGui, 'getOSManagerGui')
    dispatcher.register_function(getOSManager, 'getOSManager')
    dispatcher.register_function(createOSManager, 'createOSManager')
    dispatcher.register_function(modifyOSManager, 'modifyOSManager')
    dispatcher.register_function(removeOSManager, 'removeOSManager')
    dispatcher.register_function(testOsManager, 'testOsManager')
    dispatcher.register_function(checkOSManager, 'checkOSManager')
    
