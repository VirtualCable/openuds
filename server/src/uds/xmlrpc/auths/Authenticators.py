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
from __future__ import unicode_literals

from django.utils.translation import ugettext as _
from django.db import IntegrityError 
from uds.models import Authenticator
from Groups import getRealGroups
from uds.xmlrpc.util.Helpers import dictFromData
from uds.xmlrpc.util.Exceptions import InsertException, ParametersException, FindException, ValidationException
from uds.core.auths.Exceptions import AuthenticatorException
from uds.core import auths 
from AdminAuth import needs_credentials
from uds.core.Environment import Environment
import logging

logger = logging.getLogger(__name__)

def dictFromAuthType(type_):
    '''
    Returns a dictionary that describes the authenticator, so the administration
    interface has the info to handle it.
    
    Args:
        type_: Authenticator type (class) where to get information
        
    Returns:
        Dictionary describing the Authenticator type
    '''
    return { 'name' : type_.name(), 'type' : type_.type(), 'description' : type_.description(), 
             'icon' : type_.icon(), 'isExternalSource' : type_.isExternalSource, 
             'canSearchUsers' : type_.searchUsers != auths.Authenticator.searchUsers, 
             'canSearchGroups' : type_.searchGroups != auths.Authenticator.searchGroups,
             'needsPassword' : type_.needsPassword, 'userNameLabel' : _(type_.userNameLabel), 
             'groupNameLabel' : _(type_.groupNameLabel), 'passwordLabel' : _(type_.passwordLabel),
             'canCreateUsers' : type_.createUser != auths.Authenticator.createUser,
           }

@needs_credentials
def getAuthenticatorsTypes(credentials):
    '''
    Returns the types of authenticators registered in system
    '''
    res = []
    for _type in auths.factory().providers().values():
        res.append(dictFromAuthType(_type))
    return res

@needs_credentials
def getAuthenticators(credentials):
    '''
    Returns the services providers managed (at database)
    '''
    logger.debug("Returning authenticators...")
    res = []
    for auth in Authenticator.objects.all().order_by('priority'):
        try:
            val = { 'id' : str(auth.id), 'name' : auth.name, 'comments' : auth.comments, 'type' : auth.data_type, 'typeName' : auth.getInstance().name(), 
                   'priority' : str(auth.priority), 'smallName' : auth.small_name }
            res.append(val)
        except Exception, e:
            logger.debug("Exception: {0}".format(e))
    
    return res

@needs_credentials
def getAuthenticatorType(credentials, id):
    '''
    Return the type of an authenticator
    '''
    logger.debug('Returning authenticator type')
    try:
        auth = Authenticator.objects.get(pk=id)
        logger.debug('Auth: {0}'.format(auth))
        return dictFromAuthType(auths.factory().lookup(auth.data_type))
    except Authenticator.DoesNotExist:
        raise InsertException(_('Authenticator does not exists'))

@needs_credentials
def getAuthenticatorGui(credentials, type):
    '''
    Returns the description of an gui for the specified authenticator
    '''
    logger.debug('Authenticator type requested: {0}'.format(type))
    authType = auths.factory().lookup(type)
    return authType.guiDescription()

@needs_credentials
def getAuthenticator(credentials, id):
    '''
    Returns the specified authenticator (at database)
    '''
    data = Authenticator.objects.get(pk=id)
    res = [ 
           { 'name' : 'name', 'value' : data.name },
           { 'name' : 'comments', 'value' : data.comments },
           { 'name' : 'priority', 'value' : str(data.priority)}
          ]
    for key, value in data.getInstance().valuesDict().iteritems():
        valtext = 'value'
        if value.__class__ == list:
            valtext = 'values'
        val = {'name' : key, valtext : value }
        res.append(val)
    return res

@needs_credentials
def getAuthenticatorGroups(credentials, id):
    '''
    '''
    return getRealGroups(id)

@needs_credentials
def createAuthenticator(credentials, type, data):
    '''
    Creates a new authenticator with specified type and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    dict_ = dictFromData(data)
    # First create data without serialization, then serialies data with correct environment
    dict_['_request'] = credentials.request
    auth = None
    try:
        auth = Authenticator.objects.create(name = dict_['name'], comments = dict_['comments'], 
                                            data_type = type, priority=int(dict_['priority']), small_name=dict_['smallName'])
        auth.data = auth.getInstance(dict_).serialize()
        auth.save()
    except auths.Authenticator.ValidationException as e:
        auth.delete()
        raise ValidationException(str(e))
    except IntegrityError: # Must be exception at creation
        raise InsertException(_('Name %s already exists') % (dict_['name']))
    except Exception as e:
        logger.exception("Exception at createAuthenticator")
        logger.error(auth)
        if auth is not None:
            auth.delete()
        raise e
            
    # Returns true always, 
    return True

@needs_credentials
def modifyAuthenticator(credentials, id, data):
    '''
    Modifies an existing service provider with specified id and data
    It's mandatory that data contains at least 'name' and 'comments'.
    The expected structure is the same that provided at getServiceProvider
    '''
    try:
        auth = Authenticator.objects.get(pk=id)
        dict_ = dictFromData(data)
        dict_['_request'] = credentials.request
        a = auth.getInstance(dict_)
        auth.data = a.serialize()
        auth.name = dict_['name']
        auth.comments = dict_['comments']
        auth.priority = int(dict_['priority'])
        auth.small_name = dict_['smallName']
        auth.save()
    except auths.Authenticator.ValidationException as e:
        raise ValidationException(str(e))
    except Exception as e:
        logger.exception(e)
        raise ValidationException(str(e))
    
    return True
    
@needs_credentials
def removeAuthenticator(credentials, id):
    '''
    Removes from database authenticator with specified id
    '''
    Authenticator.objects.get(pk=id).delete()
    return True

@needs_credentials
def testAuthenticator(credentials, type, data):
    '''
    invokes the test function of the specified authenticator type, with the suplied data
    '''
    logger.debug("Testing authenticator, type: {0}, data:{1}".format(type, data))
    authType = auths.factory().lookup(type)
    # We need an "temporary" environment to test this service
    dict_ = dictFromData(data)
    dict_['_request'] = credentials.request
    res = authType.test(Environment.getTempEnv(), dict_)
    return {'ok' : res[0], 'message' : res[1]}

@needs_credentials
def checkAuthenticator(credentials, id):
    '''
    Invokes the check function of the specified authenticator
    '''
    auth = Authenticator.objects.get(id=id)
    a = auth.getInstance()
    return a.check()

@needs_credentials
def searchAuthenticator(credentials, id, srchUser, srchString):
    '''
    Search for the users that match srchString
    '''
    logger.debug("srchUser: {0}".format(srchUser))
    try:
        auth = Authenticator.objects.get(pk=id).getInstance()
        canDoSearch = srchUser is True and (auth.searchUsers != auths.Authenticator.searchUsers) or (auth.searchGroups != auths.Authenticator.searchGroups)
        if canDoSearch is False:
            raise ParametersException(_('Authenticator do not supports search'))
        if srchUser is True:
            return auth.searchUsers(srchString) 
        else:
            return auth.searchGroups(srchString)
    except Authenticator.DoesNotExist:
        raise FindException(_('Specified authenticator do not exists anymore. Please, reload gui'))
    except AuthenticatorException, e:
        raise ParametersException(str(e))
    
    raise FindException(_('BUG: Reached a point that should never have been reached!!!'))


def registerAuthenticatorFunctions(dispatcher):
    dispatcher.register_function(getAuthenticatorsTypes, 'getAuthenticatorsTypes')
    dispatcher.register_function(getAuthenticatorType, 'getAuthenticatorType')
    dispatcher.register_function(getAuthenticators, 'getAuthenticators')
    dispatcher.register_function(getAuthenticatorGui, 'getAuthenticatorGui')
    dispatcher.register_function(getAuthenticator, 'getAuthenticator')
    dispatcher.register_function(getAuthenticatorGroups, 'getAuthenticatorGroups')
    dispatcher.register_function(createAuthenticator, 'createAuthenticator')
    dispatcher.register_function(modifyAuthenticator, 'modifyAuthenticator')
    dispatcher.register_function(removeAuthenticator, 'removeAuthenticator')
    dispatcher.register_function(testAuthenticator, 'testAuthenticator')
    dispatcher.register_function(checkAuthenticator, 'checkAuthenticator')
    dispatcher.register_function(searchAuthenticator, 'searchAuthenticator')

