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

from uds.models import DeployedService, Service, OSManager, Transport, State, Group
from ..auths.AdminAuth import needs_credentials
from django.db import IntegrityError
from ..util.Exceptions import DuplicateEntryException, InsertException, FindException
from Services import infoDictFromServiceInstance
from ..auths.Groups import dictFromGroup
from ..transports.Transports import dictFromTransport

import logging

logger = logging.getLogger(__name__)


def dictFromDeployedService(srv):
    if srv.service is not None:
        service = srv.service.getInstance()
        svrName = srv.service.name
    else:
        service = None
        svrName = _('Unknown')
    if srv.osmanager is not None:
        osManagerName = srv.osmanager.name
    else:
        osManagerName = ''
    transports = []
    for trans in srv.transports.order_by('name'):
        transports.append({'id': str(trans.id), 'name': trans.name})
    groups = []
    for grp in srv.assignedGroups.order_by('name'):
        groups.append({'id': str(grp.id), 'name': grp.name})
    return {'id': str(srv.id), 'name': srv.name, 'comments': srv.comments, 'idService': str(srv.service_id),
            'idOsManager': str(srv.osmanager_id), 'initialServices': srv.initial_srvs, 'cacheL1': srv.cache_l1_srvs,
            'cacheL2': srv.cache_l2_srvs, 'maxServices': srv.max_srvs, 'state': srv.state,
            'serviceName': svrName, 'osManagerName': osManagerName,
            'transports': transports, 'groups': groups, 'info': infoDictFromServiceInstance(service)
            }


def addTransportsToDeployedService(deployedService, transports):
    '''
    Uses the dictionary transport to add transport to a deployedService.
    We simply remmoves all previous transports and add the indicated transports
    '''
    deployedService.transports.clear()
    for tr in transports:
        try:
            transport = Transport.objects.get(pk=tr['id'])
            logger.debug('Adding transport {0}'.format(transport))
            deployedService.transports.add(transport)
        except Exception:
            pass  # Silently ignore unknown transports ids
    return True


@needs_credentials
def getDeployedServices(credentials, all_):
    '''
    Returns the available deployed services
    '''
    logger.debug('Returning list of deployed services')
    res = []
    if all_ == True:
        dss = DeployedService.objects.all().order_by('name')
    else:
        dss = DeployedService.objects.filter(state=State.ACTIVE).order_by('name')
    for ds in dss:
        try:
            res.append(dictFromDeployedService(ds))
        except Exception:
            logger.exception('Exception adding deployed service')
    return res


@needs_credentials
def getDeployedService(credentials, id):
    '''
    Returns the available deployed services
    '''
    logger.debug('Returning list of deployed services')
    ds = DeployedService.objects.get(pk=id)
    if ds.state == State.ACTIVE:
        return dictFromDeployedService(ds)
    raise InsertException(_('Deployed Service does not exists'))
    
    
@needs_credentials
def createDeployedService(credentials, deployedService):
    '''
    Creates a new deployed service based on params
    '''
    logger.debug('Creating deployed service with params {0}'.format(deployedService))
    try:
        service = Service.objects.get(pk=deployedService['idService'])
        serviceInstance = service.getInstance()
        initialServices = deployedService['initialServices']
        cacheL1 = deployedService['cacheL1']
        cacheL2 = deployedService['cacheL2']
        maxServices = deployedService['maxServices']
        if serviceInstance.usesCache == False:
            initialServices = cacheL1 = cacheL2 = maxServices = 0
        osManager = None
        if serviceInstance.needsManager:
            osManager = OSManager.objects.get(pk=deployedService['idOsManager'])
        dps = DeployedService.objects.create(name = deployedService['name'], comments = deployedService['comments'], service = service, 
                                       osmanager = osManager, state = State.ACTIVE, initial_srvs = initialServices, cache_l1_srvs = cacheL1, 
                                       cache_l2_srvs = cacheL2, max_srvs = maxServices, current_pub_revision = 1)
        # Now we add transports
        addTransportsToDeployedService(dps, deployedService['transports'])
    except IntegrityError as e:
        logger.error("Integrity error adding deployed service {0}".format(e))
        raise DuplicateEntryException(deployedService['name'])
    except Exception as e:
        logger.error("Exception adding deployed service {0}".format(deployedService))
        raise InsertException(str(e))
    return str(dps.id)
    
@needs_credentials
def modifyDeployedService(credentials, deployedService):
    '''
    Modifies a deployed service
    '''
    logger.debug('Modifying deployed service'.format(deployedService))
    try:
        dps = DeployedService.objects.get(pk=deployedService['id'])
        serviceInstance = dps.service.getInstance()
        initialServices = deployedService['initialServices']
        cacheL1 = deployedService['cacheL1']
        cacheL2 = deployedService['cacheL2']
        maxServices = deployedService['maxServices']
        if serviceInstance.usesCache == False:
            initialServices = cacheL1 = cacheL2 = maxServices = 0
        
        dps.name = deployedService['name']
        dps.comments = deployedService['comments']
        dps.initial_srvs = initialServices
        dps.cache_l1_srvs = cacheL1
        dps.cache_l2_srvs = cacheL2
        dps.max_srvs = maxServices
        dps.save()
        # Now add transports
        addTransportsToDeployedService(dps, deployedService['transports'])
    except IntegrityError as e:
        logger.error("Integrity error modifiying deployed service {0}".format(e))
        raise DuplicateEntryException(deployedService['name'])
    except DeployedService.DoesNotExist:
        logger.error("Requested deployed service does not exists")
        raise InsertException(_('Deployed Service does not exists'))
    except Exception as e:
        logger.error("Exception modifiying deployed service {0}".format(deployedService))
        raise InsertException(str(e))
    return True

@needs_credentials
def getGroupsAssignedToDeployedService(credentials, deployedServiceId):
    '''
    Return groups assigned to this deployed service
    '''
    logger.debug('Returning assigned groups to deployed service {0}'.format(deployedServiceId))
    grps = []
    try:
        dps = DeployedService.objects.get(pk=deployedServiceId)
        groups = dps.assignedGroups.all()
        for grp in groups:
            grps.append(dictFromGroup(grp))
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed Service does not exists'))
    return grps

@needs_credentials
def assignGroupToDeployedService(credentials, deployedServiceId, groupId):
    '''
    Assigns a group to a deployed service
    '''
    logger.debug('Assigning group {0} to deployed service {1}'.format(groupId, deployedServiceId))
    try:
        grp = Group.objects.get(pk=groupId)
        dps = DeployedService.objects.get(pk=deployedServiceId)
        dps.assignedGroups.add(grp)
    except Group.DoesNotExist:
        raise InsertException(_('Group does not exists'))
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed Service does not exists'))
    return True

@needs_credentials
def removeGroupsFromDeployedService(credentials, deployedServiceId, groupIds):
    '''
    Removes a group from a deployed service
    '''
    logger.debug('Removing groups {0} from deployed service {1}'.format(groupIds, deployedServiceId))
    try:
        dps = DeployedService.objects.get(pk=deployedServiceId)
        dps.assignedGroups.remove(*groupIds)
        # TODO: Mark groups for this deployed services as "must clean" so services are correctly cleaned
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed Service does not exists'))
    return True

@needs_credentials
def getTransportsAssignedToDeployedService(credentias, idDS):
    '''
    Returns the transports associated with an iDS
    '''
    try:
        ds = DeployedService.objects.get(id=idDS)
        return [ dictFromTransport(t) for t in ds.transports.all() ]
    except DeployedService.DoesNotExist:
        raise FindException(_('Can\'t find deployed service'))
    except Exception as e:
        logger.exception("getTransportsForDeployedService: ")
        raise FindException(str(e))

@needs_credentials
def assignTransportToDeployedService(credentials, deployedServiceId, transportId):
    logger.debug('Assigning transport {0} to service {1}'.format(transportId, deployedServiceId))
    try:
        trans = Transport.objects.get(pk=transportId)
        dps = DeployedService.objects.get(pk=deployedServiceId)
        dps.transports.add(trans)
    except Transport.DoesNotExist:
        raise InsertException(_('Transport does not exists'))
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed Service does not exists'))
        
    return True

@needs_credentials
def removeTransportFromDeployedService(credentials, deployedServiceId, transportIds):
    '''
    Removes a group from a deployed service
    '''
    logger.debug('Removing transports {1} from deployed service {1}'.format(transportIds, deployedServiceId))
    try:
        dps = DeployedService.objects.get(pk=deployedServiceId)
        dps.transports.remove(*transportIds)
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed Service does not exists'))
    return True

    
@needs_credentials
def removeDeployedService(credentials, deployedServiceId):
    '''
    Removes a deployed service
    '''
    # First, mark all services as removable
    logger.debug('Removing deployed service {0}'.format(deployedServiceId))
    try:
        ds = DeployedService.objects.get(pk=deployedServiceId)
        ds.remove()
    except DeployedService.DoesNotExist:
        raise InsertException(_('Deployed service does not exists'))
    return True

# Registers XML RPC Methods
def registerDeployedServicesFunctions(dispatcher):
    dispatcher.register_function(getDeployedServices, 'getDeployedServices')
    dispatcher.register_function(getDeployedService, 'getDeployedService')
    dispatcher.register_function(createDeployedService, 'createDeployedService')
    dispatcher.register_function(modifyDeployedService, 'modifyDeployedService')
    dispatcher.register_function(assignGroupToDeployedService, 'assignGroupToDeployedService')
    dispatcher.register_function(removeGroupsFromDeployedService, 'removeGroupsFromDeployedService')
    dispatcher.register_function(getGroupsAssignedToDeployedService, 'getGroupsAssignedToDeployedService')
    dispatcher.register_function(assignTransportToDeployedService, 'assignTransportToDeployedService')
    dispatcher.register_function(removeTransportFromDeployedService, 'removeTransportFromDeployedService')
    dispatcher.register_function(getTransportsAssignedToDeployedService, 'getTransportsAssignedToDeployedService')
    dispatcher.register_function(removeDeployedService, 'removeDeployedService')
