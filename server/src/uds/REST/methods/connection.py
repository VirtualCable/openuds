# -*- coding: utf-8 -*-

#
# Copyright (c) 2015 Virtual Cable S.L.
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

from uds.REST import Handler
from uds.REST import RequestError
from uds.models import UserService, DeployedService, Transport
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core.util import log
from uds.core.util.stats import events


import datetime
import six

import logging

logger = logging.getLogger(__name__)


# Enclosed methods under /actor path
class Connection(Handler):
    '''
    Processes actor requests
    '''
    authenticated = True  # Actor requests are not authenticated
    needs_admin = False
    needs_staff = False

    @staticmethod
    def result(result=None, error=None):
        '''
        Helper method to create a "result" set for connection response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        '''
        result = result if result is not None else ''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            res['error'] = error
        return res

    def serviceList(self):
        # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
        groups = list(self._user.getGroups())
        availServices = DeployedService.getDeployedServicesForGroups(groups)
        availUserServices = UserService.getUserAssignedServices(self._user)

        # Extract required data to show to user
        services = []
        # Select assigned user services
        for svr in availUserServices:
            # Skip maintenance services...
            trans = []
            for t in svr.transports.all().order_by('priority'):
                typeTrans = t.getType()
                if t.validForIp(self._request.ip) and t.getType().providesConnetionInfo():
                    trans.append({'id': t.uuid, 'name': t.name, 'needsJava': t.getType().needsJava})
            services.append({'id': 'A' + svr.uuid,
                             'name': svr['name'],
                             'transports': trans,
                             'maintenance': svr.deployed_service.service.provider.maintenance_mode,
                             'in_use': svr.in_use})

        logger.debug(services)

        # Now generic user service
        for svr in availServices:
            trans = []
            for t in svr.transports.all().order_by('priority'):
                if t.validForIp(self._request.ip) and t.getType().providesConnetionInfo():
                    typeTrans = t.getType()
                    trans.append({'id': t.uuid, 'name': t.name, 'needsJava': typeTrans.needsJava})

            # Locate if user service has any already assigned user service for this
            ads = UserServiceManager.manager().getExistingAssignationForUser(svr, self._user)
            if ads is None:
                in_use = False
            else:
                in_use = ads.in_use

            services.append({'id': 'F' + svr.uuid,
                             'name': svr.name,
                             'transports': trans,
                             'maintenance': svr.service.provider.maintenance_mode,
                             'in_use': in_use})

        logger.debug('Services: {0}'.format(services))

        services = sorted(services, key=lambda s: s['name'].upper())

        return Connection.result(result=services)

    def connection(self, doNotCheck=False):
        kind, idService = self._args[0][0], self._args[0][1:]
        idTransport = self._args[1]

        logger.debug('Type: {}, Service: {}, Transport: {}'.format(kind, idService, idTransport))

        try:
            logger.debug('Kind of service: {0}, idService: {1}'.format(kind, idService))
            if kind == 'A':  # This is an assigned service
                ads = UserService.objects.get(uuid=idService)
            else:
                ds = DeployedService.objects.get(uuid=idService)
                # We first do a sanity check for this, if the user has access to this service
                # If it fails, will raise an exception
                ds.validateUser(self._user)
                # Now we have to locate an instance of the service, so we can assign it to user.
                ads = UserServiceManager.manager().getAssignationForUser(ds, self._user)

            if ads.isInMaintenance() is True:
                return Connection.result(error='Service in maintenance')

            logger.debug('Found service: {0}'.format(ads))
            trans = Transport.objects.get(uuid=idTransport)

            if trans.validForIp(self._request.ip) is False:
                return Connection.result(error='Access denied')

            # Test if the service is ready
            if doNotCheck or ads.isReady():
                log.doLog(ads, log.INFO, "User {0} from {1} has initiated access".format(self._user.name, self._request.ip), log.WEB)
                # If ready, show transport for this service, if also ready ofc
                iads = ads.getInstance()
                ip = iads.getIp()
                logger.debug('IP: {}'.format(ip))
                events.addEvent(ads.deployed_service, events.ET_ACCESS, username=self._user.name, srcip=self._request.ip, dstip=ip, uniqueid=ads.unique_id)
                if ip is not None:
                    itrans = trans.getInstance()
                    if itrans.providesConnetionInfo() and (doNotCheck or itrans.isAvailableFor(ip)):
                        ads.setConnectionSource(self._request.ip, 'unknown')
                        log.doLog(ads, log.INFO, "User service ready, rendering transport", log.WEB)

                        ci = {
                            'username': '',
                            'password': '',
                            'domain': '',
                            'protocol': 'unknown',
                            'ip': ip
                        }
                        ci.update(itrans.getConnectionInfo(ads, self._user, 'UNKNOWN'))

                        UserServiceManager.manager().notifyPreconnect(ads, itrans.processedUser(ads, self._user), itrans.protocol)

                        return Connection.result(result=ci)
                    else:
                        log.doLog(ads, log.WARN, "User service is not accessible by REST (ip {0})".format(ip), log.TRANSPORT)
                        logger.debug('Transport {} is not accesible for user service {} from {}'.format(trans, ads, self._request.ip))
                        logger.debug("{}, {}".format(itrans.providesConnetionInfo(), itrans.isAvailableFor(ip)))
                else:
                    logger.debug('Ip not available from user service {0}'.format(ads))
            else:
                log.doLog(ads, log.WARN, "User {0} from {1} tried to access, but service was not ready".format(self._user.name, self._request.ip), log.WEB)
            # Not ready, show message and return to this page in a while
            return Connection.result(error='Service not ready')
        except Exception as e:
            return Connection.result(error=six.text_type(e))

    def get(self):
        '''
        Processes get requests
        '''
        logger.debug("Connection args for GET: {0}".format(self._args))

        if len(self._args) == 0:
            # Return list of services/transports
            return self.serviceList()

        if len(self._args) == 2:
            # Return connection & validate access for service/transport
            return self.connection()

        if len(self._args) == 3 and self._args[2] == 'skipChecking':
            return self.connection(True)

        raise RequestError('Invalid Request')
