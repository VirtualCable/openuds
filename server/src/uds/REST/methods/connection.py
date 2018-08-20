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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext as _

from uds.REST import Handler
from uds.REST import RequestError
from uds.models import UserService, DeployedService, ServicesPoolGroup
from uds.core.managers import userServiceManager
from uds.core.managers import cryptoManager
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.Config import GlobalConfig
from uds.core.services.Exceptions import ServiceNotReadyError
from uds.web import errors

import datetime
import six

import logging

logger = logging.getLogger(__name__)


# Enclosed methods under /connection path
class Connection(Handler):
    """
    Processes actor requests
    """
    authenticated = True  # Actor requests are not authenticated
    needs_admin = False
    needs_staff = False

    @staticmethod
    def result(result=None, error=None, errorCode=0, retryable=False):
        """
        Helper method to create a "result" set for connection response
        :param result: Result value to return (can be None, in which case it is converted to empty string '')
        :param error: If present, This response represents an error. Result will contain an "Explanation" and error contains the error code
        :return: A dictionary, suitable for response to Caller
        """
        result = result if result is not None else ''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            if isinstance(error, int):
                error = errors.errorString(error)
            if errorCode != 0:
                error += ' (code {0:04X})'.format(errorCode)
            res['error'] = error

        res['retryable'] = retryable and '1' or '0'

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
                if t.validForIp(self._request.ip) and t.getType().providesConnetionInfo():
                    trans.append({'id': t.uuid, 'name': t.name})

            servicePool = svr.deployed_service

            services.append({'id': 'A' + svr.uuid,
                             'name': servicePool.name,
                             'description': servicePool.comments,
                             'visual_name': servicePool.visual_name,
                             'group': servicePool.servicesPoolGroup if servicePool.servicesPoolGroup is not None else ServicesPoolGroup.default().as_dict,
                             'thumb': servicePool.image.thumb64 if servicePool.image is not None else DEFAULT_THUMB_BASE64,
                             'show_transports': servicePool.show_transports,
                             'allow_users_remove': servicePool.allow_users_remove,
                             'not_accesible': not servicePool.isAccessAllowed(),
                             'to_be_replaced': False,  # Manually assigned will not be autoremoved never
                             'transports': trans,
                             'maintenance': servicePool.isInMaintenance(),
                             'in_use': servicePool.in_use})

        logger.debug(services)

        # Now generic user service
        for servicePool in availServices:
            trans = []
            for t in servicePool.transports.all().order_by('priority'):
                if t.validForIp(self._request.ip) and t.getType().providesConnetionInfo():
                    trans.append({'id': t.uuid, 'name': t.name})

            # Locate if user service has any already assigned user service for this
            ads = userServiceManager().getExistingAssignationForUser(servicePool, self._user)
            if ads is None:
                in_use = False
            else:
                in_use = ads.in_use

            services.append({'id': 'F' + servicePool.uuid,
                             'name': servicePool.name,
                             'description': servicePool.comments,
                             'visual_name': servicePool.visual_name,
                             'group': servicePool.servicesPoolGroup if servicePool.servicesPoolGroup is not None else ServicesPoolGroup.default().as_dict,
                             'thumb': servicePool.image.thumb64 if servicePool.image is not None else DEFAULT_THUMB_BASE64,
                             'show_transports': servicePool.show_transports,
                             'allow_users_remove': servicePool.allow_users_remove,
                             'not_accesible': not servicePool.isAccessAllowed(),
                             'to_be_replaced': servicePool.toBeReplaced(),
                             'transports': trans,
                             'maintenance': servicePool.isInMaintenance(),
                             'in_use': in_use})

        logger.debug('Services: {0}'.format(services))

        services = sorted(services, key=lambda s: s['name'].upper())

        return Connection.result(result=services)

    def connection(self, doNotCheck=False):
        idService = self._args[0]
        idTransport = self._args[1]
        try:
            ip, userService, iads, trans, itrans = userServiceManager().getService(self._user, self._request.ip, idService, idTransport, not doNotCheck)
            ci = {
                'username': '',
                'password': '',
                'domain': '',
                'protocol': 'unknown',
                'ip': ip
            }
            if doNotCheck is False:
                ci.update(itrans.getConnectionInfo(userService, self._user, 'UNKNOWN'))
            return Connection.result(result=ci)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=six.text_type(e))

    def script(self):
        idService = self._args[0]
        idTransport = self._args[1]
        scrambler = self._args[2]
        hostname = self._args[3]

        try:
            res = userServiceManager().getService(self._user, self._request.ip, idService, idTransport)
            logger.debug('Res: {}'.format(res))
            ip, userService, userServiceInstance, transport, transportInstance = res
            password = cryptoManager().symDecrpyt(self.getValue('password'), scrambler)

            userService.setConnectionSource(self._request.ip, hostname)  # Store where we are accessing from so we can notify Service

            transportScript = transportInstance.getEncodedTransportScript(userService, transport, ip, self._request.os, self._user, password, self._request)

            return Connection.result(result=transportScript)
        except ServiceNotReadyError as e:
            # Refresh ticket and make this retrayable
            return Connection.result(error=errors.SERVICE_IN_PREPARATION, errorCode=e.code, retryable=True)
        except Exception as e:
            logger.exception("Exception")
            return Connection.result(error=six.text_type(e))

        return password

    def get(self):
        """
        Processes get requests
        """
        logger.debug("Connection args for GET: {0}".format(self._args))

        if len(self._args) == 0:
            # Return list of services/transports
            return self.serviceList()
        if len(self._args) == 1:
            # Maybe we are requesting a ticket content?
            return self.getTicketContent()

        if len(self._args) == 2:
            # Return connection & validate access for service/transport
            return self.connection()

        if len(self._args) == 3:
            # /connection/idService/idTransport/skipChecking
            if self._args[2] == 'skipChecking':
                return self.connection(True)

        if len(self._args) == 4:
            # /connection/idService/idTransport/scrambler/hostname
            return self.script()

        raise RequestError('Invalid Request')
