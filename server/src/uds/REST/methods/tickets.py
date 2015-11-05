# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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

from uds.REST import Handler
from uds.REST import RequestError
from uds.models import Authenticator
from uds.models import DeployedService
from uds.models import Transport
from uds.models import TicketStore
from uds.core.util.model import processUuid
from uds.core.util import tools

import datetime
import six

import logging

logger = logging.getLogger(__name__)

VALID_PARAMS = ('authId', 'authTag', 'authSmallName', 'auth', 'username', 'realname', 'password', 'groups', 'servicePool', 'transport', 'force', 'userIp')


# Enclosed methods under /actor path
class Tickets(Handler):
    '''
    Processes tickets access requests.
    Tickets are element used to "register" & "allow access" to users.

    The rest API accepts the following parameters:
       authId: uuid of the authenticator for the user                |  Mutually excluyents
       authSmallName: tag of the authenticator (alias for "authTag") |  But must include one of theese
       authTag: tag of the authenticator                             |
       auth: Name of authenticator                                   |
       userIp: Direccion IP del cliente. Si no se pasa, no se puede filtar
       username:
       password:
       groups:
       servicePool:
       transport:
       force:  If "1" or "true" will ensure that:
                 - Groups exists on authenticator
                 - servicePool has these groups in it's allowed list
    '''
    needs_admin = True  # By default, staff is lower level needed

    @staticmethod
    def result(result='', error=None):
        '''
        Returns a result for a Ticket request
        '''
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            res['error'] = error
        return res

    def get(self):
        '''
        Processes get requests, currently none
        '''
        logger.debug("Ticket args for GET: {0}".format(self._args))

        raise RequestError('Invalid request')

    # Must be invoked as '/rest/ticket/create, with "username", ("authId" or ("authSmallName" or "authTag"), "groups" (array) and optionally "time" (in seconds) as paramteres
    def put(self):
        '''
        Processes put requests, currently only under "create"
        '''
        logger.debug(self._args)

        # Parameters can only be theese

        for p in self._params:
            if p not in VALID_PARAMS:
                logger.debug('Parameter {} not in valid ticket parameters list'.format(p))
                raise RequestError('Invalid parameters')

        if len(self._args) != 1 or self._args[0] not in ('create',):
            raise RequestError('Invalid method')

        if 'username' not in self._params or 'groups' not in self._params:
            raise RequestError('Invalid parameters')

        found = None
        for i in ('authId', 'authTag', 'auth', 'authSmallName'):
            if i in self._params:
                found = i
                break

        if found is None:
            raise RequestError('Invalid parameters (no auth)')

        force = self._params.get('force', '0') in ('1', 'true', 'True')

        userIp = self._params.get('userIp', None)

        try:
            authId = self._params.get('authId', None)
            authTag = self._params.get('authTag', self._params.get('authSmallName', None))
            authName = self._params.get('auth', None)

            # Will raise an exception if no auth found
            if authId is not None:
                auth = Authenticator.objects.get(uuid=processUuid(authId.lower()))
            elif authName is not None:
                auth = Authenticator.objects.get(name=authName)
            else:
                auth = Authenticator.objects.get(small_name=authTag)

            username = self._params['username']
            password = self._params.get('password', '')  # Some machines needs password, depending on configuration
            groups = self._params['groups']
            if isinstance(groups, (six.text_type, six.binary_type)):
                groups = (groups,)
            grps = []
            for g in groups:
                try:
                    grps.append(auth.groups.get(name=g).uuid)
                except Exception:
                    logger.info('Group {} from ticket does not exists on auth {}, forced creation: {}'.format(g, auth, force))
                    if force:
                        grps.append(auth.groups.create(name=g, comments='Autocreated form ticket by using force paratemeter').uuid)

            if len(grps) == 0:  # No valid group in groups names
                raise Exception('Authenticator does not contain ANY of the requested groups')

            groups = grps

            time = int(self._params.get('time', 60))
            time = 60 if time < 1 else time
            realname = self._params.get('realname', self._params['username'])
            servicePool = self._params.get('servicePool', None)

            transport = self._params.get('transport', None)

            if servicePool is not None:
                servicePool = DeployedService.objects.get(uuid=processUuid(servicePool))

                # If forced that servicePool must honor groups
                if force:
                    for addGrp in set(groups) - set(servicePool.assignedGroups.values_list('uuid', flat=True)):
                        servicePool.assignedGroups.add(auth.groups.get(uuid=addGrp))

                if transport is not None:
                    transport = Transport.objects.get(uuid=processUuid(transport))
                    try:
                        servicePool.validateTransport(transport)
                    except Exception:
                        logger.error('Transport {} is not valid for Service Pool {}'.format(transport.name, servicePool.name))
                        raise Exception('Invalid transport for Service Pool')
                else:
                    if userIp is None:
                        transport = tools.DictAsObj({'uuid': None})
                    else:
                        transport = None
                        for v in servicePool.transports.order_by('priority'):
                            if v.validForIp(userIp):
                                transport = v
                                break

                        if transport is None:
                            logger.error('Service pool {} does not has valid transports for ip {}'.format(servicePool.name, userIp))
                            raise Exception('Service pool does not has any valid transports for ip {}'.format(userIp))

                servicePool = servicePool.uuid
                transport = transport.uuid  # pylint: disable=maybe-no-member

        except Authenticator.DoesNotExist:
            return Tickets.result(error='Authenticator does not exists')
        except DeployedService.DoesNotExist:
            return Tickets.result(error='Service pool does not exists')
        except Transport.DoesNotExist:
            return Tickets.result(error='Transport does not exists')
        except Exception as e:
            return Tickets.result(error=six.text_type(e))

        data = {
            'username': username,
            'password': password,
            'realname': realname,
            'groups': groups,
            'auth': auth.uuid,
            'servicePool': servicePool,
            'transport': transport,
        }

        ticket = TicketStore.create(data)

        return Tickets.result(ticket)
