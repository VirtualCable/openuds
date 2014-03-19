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
from uds.models import Provider
from uds.core.services.ServiceProviderFactory import ServiceProviderFactory
from ..util.Helpers import dictFromData
from ..util.Exceptions import ValidationException, InsertException, FindException, DeleteException
from ..auths.AdminAuth import needs_credentials
from uds.core.Environment import Environment
import logging
from uds.core import services

logger = logging.getLogger(__name__)


@needs_credentials
def getServiceProvidersTypes(credentials):
    '''
    Returns the types of services providers registered in system
    '''
    res = []
    for type_ in ServiceProviderFactory.factory().providers().values():
        val = { 'name' : _(type_.name()), 'type' : type_.type(), 'description' : _(type_.description()), 'icon' : type_.icon() }
        res.append(val)
    return res


@needs_credentials
def getServiceProviders(credentials):
    '''
    Returns the services providers managed (at database)
    '''
    res = []
    for prov in Provider.objects.order_by('name'):
        try:
            val = { 'id' : str(prov.id), 'name' : prov.name, 'comments' : prov.comments, 'type' : prov.data_type, 'typeName' : _(prov.getInstance().name()) }
            res.append(val)
        except Exception:
            pass
    return res


@needs_credentials
def getServiceProviderGui(credentials, type_):
    '''
    Returns the description of an gui for the specified service provider
    '''
    spType = ServiceProviderFactory.factory().lookup(type_)
    return spType.guiDescription()


@needs_credentials
def getServiceProvider(credentials, id_):
    '''
    Returns the specified service provider (at database)
    '''
    data = Provider.objects.get(pk=id_)
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
def createServiceProvider(credentials, type_, data):
    '''
    Creates a new service provider with specified type and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    try:
        dic = dictFromData(data)
        # First create data without serialization, then serialies data with correct environment
        sp = Provider.objects.create(name=dic['name'], comments=dic['comments'], data_type=type_)
        sp.data = sp.getInstance(dic).serialize()
        sp.save()
    except services.ServiceProvider.ValidationException as e:
        sp.delete()
        raise ValidationException(str(e))
    except IntegrityError:  # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dic['name']))
    except Exception as e:
        logger.exception('Unexpected exception')
        raise ValidationException(str(e))
    return True


@needs_credentials
def modifyServiceProvider(credentials, id_, data):
    '''
    Modifies an existing service provider with specified id and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    try:
        prov = Provider.objects.get(pk=id_)
        dic = dictFromData(data)
        sp = prov.getInstance(dic)
        prov.data = sp.serialize()
        prov.name = dic['name']
        prov.comments = dic['comments']
        prov.save()
    except services.ServiceProvider.ValidationException as e:
        raise ValidationException(str(e))
    except IntegrityError:  # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dic['name']))
    except Exception as e:
        logger.exception('Unexpected exception')
        raise ValidationException(str(e))

    return True


@needs_credentials
def removeServiceProvider(credentials, id_):
    '''
    Removes from database provider with specified id
    '''
    try:
        prov = Provider.objects.get(pk=id_)
        if prov.services.count() > 0:
            raise DeleteException(_('Can\'t delete service provider with services associated'))
        prov.delete()
    except Provider.DoesNotExist:
        raise FindException(_('Can\'t locate the service provider') + '.' + _('Please, refresh interface'))
    return True


@needs_credentials
def getOffersFromServiceProvider(credentials, type_):
    '''
    Returns the services offered from the provider
    '''
    spType = ServiceProviderFactory.factory().lookup(type_)
    res = []
    for t in spType.getServicesTypes():
        val = { 'name' : _(t.name()), 'type' : t.type(), 'description' : _(t.description()), 'icon' : t.icon() }
        res.append(val)
    return res


@needs_credentials
def testServiceProvider(credentials, type_, data):
    '''
    invokes the test function of the specified service provider type, with the suplied data
    '''
    logger.debug("Testing service provider, type: {0}, data:{1}".format(type, data))
    spType = ServiceProviderFactory.factory().lookup(type_)
    # We need an "temporary" environment to test this service
    dct = dictFromData(data)
    res = spType.test(Environment.getTempEnv(), dct)
    return {'ok' : res[0], 'message' : res[1]}


@needs_credentials
def checkServiceProvider(credentials, id_):
    '''
    Invokes the check function of the specified service provider
    '''
    prov = Provider.objects.get(id=id_)
    sp = prov.getInstance()
    return sp.check()


# Registers XML RPC Methods
def registerServiceProvidersFunctions(dispatcher):
    dispatcher.register_function(getServiceProvidersTypes, 'getServiceProvidersTypes')
    dispatcher.register_function(getServiceProviders, 'getServiceProviders')
    dispatcher.register_function(getServiceProviderGui, 'getServiceProviderGui')
    dispatcher.register_function(getServiceProvider, 'getServiceProvider')
    dispatcher.register_function(createServiceProvider, 'createServiceProvider')
    dispatcher.register_function(modifyServiceProvider, 'modifyServiceProvider')
    dispatcher.register_function(removeServiceProvider, 'removeServiceProvider')
    dispatcher.register_function(getOffersFromServiceProvider, 'getOffersFromServiceProvider')
    dispatcher.register_function(testServiceProvider, 'testServiceProvider')
    dispatcher.register_function(checkServiceProvider, 'checkServiceProvider')

