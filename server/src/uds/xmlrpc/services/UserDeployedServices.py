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

from uds.models import DeployedService, State, User, UserService
from django.utils.translation import ugettext as _
from ..auths.AdminAuth import needs_credentials
from ..util.Exceptions import  FindException
from uds.core.managers.UserServiceManager import UserServiceManager
import logging

logger = logging.getLogger(__name__)

def dictFromCachedDeployedService(cs):
    if cs.publication is not None:
        revision = str(cs.publication.revision)
    else:
        revision = ''

    res = { 'idParent' : str(cs.deployed_service_id), 'id' : str(cs.id), 'uniqueId' : cs.unique_id, 'friendlyName' : cs.friendly_name, 'state' : cs.state, 'osState': cs.os_state, 'stateDate' : cs.state_date, 
            'creationDate' : cs.creation_date, 'cacheLevel' : str(cs.cache_level), 'revision' : revision }
    return res

def dictFromAssignedDeployedService(ads):
    if ads.publication is not None:
        revision = str(ads.publication.revision)
    else:
        revision = ''
    
    res = { 'idParent' : str(ads.deployed_service_id), 'id' : str(ads.id), 'uniqueId' : ads.unique_id, 'friendlyName' : ads.friendly_name, 'state' : ads.state, 'osState': ads.os_state, 'stateDate' : ads.state_date, 
            'creationDate' : ads.creation_date, 'revision' : revision, 'user': ads.user.manager.name + "-" + ads.user.name, 'inUse': ads.in_use, 'inUseDate': ads.in_use_date,
            'sourceHost' : ads.src_hostname, 'sourceIp': ads.src_ip }
    return res

@needs_credentials
def getCachedDeployedServices(credentials, idParent):
    
    dps = DeployedService.objects.get(pk=idParent)
    
    res = []
    for cache in dps.cachedUserServices().order_by('-creation_date'):
        try:
            val = dictFromCachedDeployedService(cache)
            res.append(val)
        except Exception, e:
            logger.debug(e)
    return res

@needs_credentials
def getAssignedDeployedServices(credentials, idParent):
    
    dps = DeployedService.objects.get(pk=idParent)
    
    res = []
    for assigned in dps.assignedUserServices().order_by('-creation_date'):
        try:
            val = dictFromAssignedDeployedService(assigned)
            res.append(val)
        except Exception, e:
            logger.debug(e)
    logger.debug(res)
    return res

@needs_credentials
def getAssignableDeployedServices(crecentials, idParent):
    
    res = []
    try:
        dps = DeployedService.objects.get(pk=idParent)
        if dps.state != State.ACTIVE:
            raise FindException(_('The deployed service is not active'))
        servInstance = dps.service.getInstance()
        if servInstance.mustAssignManually is False:
            raise FindException(_('This service don\'t allows assignations'))
        assignables = servInstance.requestServicesForAssignation()
        for ass in assignables:
            res.append( {'id' : ass.getName(), 'name' : ass.getName() } )
    except DeployedService.DoesNotExist:
        raise FindException(_('Deployed service not found!!! (refresh interface)'))
    return res

@needs_credentials
def assignDeployedService(credentials, idParent, idDeployedUserService, idUser):
    try:
        dps = DeployedService.objects.get(pk=idParent)
        if dps.state != State.ACTIVE:
            raise FindException(_('The deployed service is not active'))
        servInstance = dps.service.getInstance()
        if servInstance.mustAssignManually is False:
            raise FindException(_('This service don\'t allows assignations'))
        user = dps.authenticator.users.get(pk=idUser)
        assignables = servInstance.requestServicesForAssignation()
        for ass in assignables:
            if ass.getName() == idDeployedUserService: # Found, create it
                UserServiceManager.manager().createAssignable(dps, ass, user)
    except DeployedService.DoesNotExist:
        raise FindException(_('Deployed service not found!!! (refresh interface)'))
    except User.DoesNotExist:
        raise FindException(_('User not found!!! (refresh interface)'))
        
    return True

@needs_credentials
def removeUserService(cretentials, ids):
    try:
        for service in UserService.objects.filter(id__in=ids):
            if service.state == State.USABLE:
                service.remove()
            elif service.state == State.PREPARING:
                service.cancel()
    except Exception:
        logger.exception("Exception at removeUserService:")
        return False
    return True

@needs_credentials
def getUserDeployedServiceError(credentials, idService):
    error = _('No error')
    try:
        uds = UserService.objects.get(pk=idService)
        if uds.state == State.ERROR:
            error = uds.getInstance().reasonOfError()
    except UserService.DoesNotExist:
        raise FindException(_('User deployed service not found!!!'))
    return error

@needs_credentials
def develAction(credentials, action, ids ):
    logger.debug('Devel action invoked: {0} for {1}'.format(action, ids))
    try:
        for uds in UserService.objects.filter(id__in=ids):
            if action == "inUse":
                logger.debug('Setting {0} to in use'.format(uds.friendly_name))
                uds.setInUse(True)
            elif action == "releaseInUse":
                logger.debug('Releasing in use from {0}'.format(uds.friendly_name))
                uds.setState(State.USABLE)
                uds.setInUse(False)
            elif action == 'notifyReady':
                logger.debug('Notifying ready from os manager to {0}'.format(uds.friendly_name))
                uds.getInstance().osmanager().process(uds, 'ready', '{0}=1.2.3.4'.format(uds.unique_id))
            else:
                logger.debug('Setting {0} to usable'.format(uds.friendly_name))
                uds.setState(State.USABLE)
                if uds.needsOsManager():
                    uds.setOsState(State.USABLE)
            uds.save()
    except UserService.DoesNotExist:
        raise FindException(_('User deployed service not found!!!'))
    return True

# Registers XML RPC Methods
def registerUserDeployedServiceFunctions(dispatcher):
    dispatcher.register_function(getCachedDeployedServices, 'getCachedDeployedServices')
    dispatcher.register_function(getAssignedDeployedServices, 'getAssignedDeployedServices')
    dispatcher.register_function(getAssignableDeployedServices, 'getAssignableDeployedServices')
    dispatcher.register_function(assignDeployedService, 'assignDeployedService')
    dispatcher.register_function(removeUserService, 'removeUserService')
    dispatcher.register_function(getUserDeployedServiceError, 'getUserDeployedServiceError')
    dispatcher.register_function(develAction, "develAction")
