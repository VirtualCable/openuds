# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import datetime
import logging
import typing


from uds.REST import Handler
from uds.REST import RequestError
from uds import models
from uds.core.managers import cryptoManager
from uds.core.util.model import processUuid
from uds.core.util import tools

logger = logging.getLogger(__name__)

VALID_PARAMS = (
    'authId', 'authTag', 'authSmallName', 'auth', 'username',
    'realname', 'password', 'groups', 'servicePool', 'transport',
    'force', 'userIp'
)


# Enclosed methods under /actor path
class Tickets(Handler):
    """
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
    """
    needs_admin = True  # By default, staff is lower level needed

    @staticmethod
    def result(result: str = '', error: typing.Optional[str] = None) -> typing.Dict[str, typing.Any]:
        """
        Returns a result for a Ticket request
        """
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            res['error'] = error
        return res

    def get(self):
        """
        Processes get requests, currently none
        """
        logger.debug('Ticket args for GET: %s', self._args)

        raise RequestError('Invalid request')

    def _checkInput(self) -> None:
        # Parameters can only be theese
        for p in self._params:
            if p not in VALID_PARAMS:
                logger.debug('Parameter %s not in valid ticket parameters list', p)
                raise RequestError('Invalid parameters')

        if len(self._args) != 1 or self._args[0] not in ('create',):
            raise RequestError('Invalid method')

        authParameter: typing.Optional[str] = None
        for i in ('authId', 'authTag', 'auth', 'authSmallName'):
            if i in self._params:
                authParameter = i
                break

        if authParameter is None:
            raise RequestError('Invalid parameters (no auth)')

    # Must be invoked as '/rest/ticket/create, with "username", ("authId" or ("authSmallName" or "authTag"), "groups" (array) and optionally "time" (in seconds) as paramteres
    def put(self):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Processes put requests, currently only under "create"
        """
        logger.debug(self._args)

        # Check that call is correct (pamateters, args, ...)
        self._checkInput()

        if 'username' not in self._params or 'groups' not in self._params:
            raise RequestError('Invalid parameters')

        force: bool = self._params.get('force', '0') in ('1', 'true', 'True')

        userIp: typing.Optional[str] = self._params.get('userIp', None)

        try:
            servicePoolId = None
            transportId = None

            authId = self._params.get('authId', None)
            authName = self._params.get('auth', None)
            authTag = self._params.get('authTag', self._params.get('authSmallName', None))

            # Will raise an exception if no auth found
            if authId:
                auth = models.Authenticator.objects.get(uuid=processUuid(authId.lower()))
            elif authName:
                auth = models.Authenticator.objects.get(name=authName)
            else:
                auth = models.Authenticator.objects.get(small_name=authTag)

            username: str = self._params['username']
            password: str = self._params.get('password', '')  # Some machines needs password, depending on configuration

            groupIds: typing.List[str] = []
            for groupName in tools.asList(self._params['groups']):
                try:
                    groupIds.append(auth.groups.get(name=groupName).uuid)
                except Exception:
                    logger.info('Group %s from ticket does not exists on auth %s, forced creation: %s', groupName, auth, force)
                    if force:  # Force creation by call
                        groupIds.append(auth.groups.create(name=groupName, comments='Autocreated form ticket by using force paratemeter').uuid)

            if not groupIds:  # No valid group in groups names
                raise RequestError('Authenticator does not contain ANY of the requested groups and force is not used')

            time = int(self._params.get('time', 60))
            time = 60 if time < 1 else time
            realname: str = self._params.get('realname', self._params['username'])

            if 'servicePool' in self._params:
                # Check if is pool or metapool
                poolUuid = processUuid(self._params['servicePool'])
                pool : typing.Union[models.ServicePool, models.MetaPool]

                try:
                    pool = typing.cast(models.MetaPool, models.MetaPool.objects.get(uuid=poolUuid))  # If not an metapool uuid, will process it as a servicePool
                    if force:
                        # First, add groups to metapool
                        for addGrp in set(groupIds) - set(pool.assignedGroups.values_list('uuid', flat=True)):
                            pool.assignedGroups.add(auth.groups.get(uuid=addGrp))
                        # And now, to ALL metapool members
                        for memberPool in pool.members.all():
                            # First, add groups to metapool
                            for addGrp in set(groupIds) - set(memberPool.assignedGroups.values_list('uuid', flat=True)):
                                memberPool.assignedGroups.add(auth.groups.get(uuid=addGrp))
                            
                    # For metapool, transport is ignored..

                    servicePoolId = 'M' + pool.uuid
                    transportId = 'meta'
                    
                except models.MetaPool.DoesNotExist:
                    pool = typing.cast(models.ServicePool, models.ServicePool.objects.get(uuid=poolUuid))

                    # If forced that servicePool must honor groups
                    if force:
                        for addGrp in set(groupIds) - set(pool.assignedGroups.values_list('uuid', flat=True)):
                            pool.assignedGroups.add(auth.groups.get(uuid=addGrp))

                    if 'transport' in self._params:
                        transport: models.Transport = models.Transport.objects.get(uuid=processUuid(self._params['transport']))
                        try:
                            pool.validateTransport(transport)
                        except Exception:
                            logger.error('Transport %s is not valid for Service Pool %s', transport.name, pool.name)
                            raise Exception('Invalid transport for Service Pool')
                    else:
                        transport = models.Transport(uuid=None)
                        if userIp:
                            for v in pool.transports.order_by('priority'):
                                if v.validForIp(userIp):
                                    transport = v
                                    break

                            if transport.uuid is None:
                                logger.error('Service pool %s does not has valid transports for ip %s', pool.name, userIp)
                                raise Exception('Service pool does not has any valid transports for ip {}'.format(userIp))

                    servicePoolId = 'F' + pool.uuid
                    transportId = transport.uuid
            
        except models.Authenticator.DoesNotExist:
            return Tickets.result(error='Authenticator does not exists')
        except models.ServicePool.DoesNotExist:
            return Tickets.result(error='Service pool (or metapool) does not exists')
        except models.Transport.DoesNotExist:
            return Tickets.result(error='Transport does not exists')
        except Exception as e:
            return Tickets.result(error=str(e))

        data = {
            'username': username,
            'password': cryptoManager().encrypt(password),
            'realname': realname,
            'groups': groupIds,
            'auth': auth.uuid,
            'servicePool': servicePoolId,
            'transport': transportId,
        }

        ticket = models.TicketStore.create(data)

        return Tickets.result(ticket)
