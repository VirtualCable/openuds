# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
from uds import models
from uds.core.managers.crypto import CryptoManager
from uds.core.util.model import process_uuid
from uds.core.util import ensure
from uds.core import exceptions

logger = logging.getLogger(__name__)

# Valid parameters accepted by ticket creation method
VALID_PARAMS = (
    'authId',
    'auth_id',
    'authTag',
    'auth_tag',
    'authSmallName',
    'auth',
    'auth_name',
    'username',
    'realname',
    'password',
    'groups',
    'servicePool',
    'service_pool',
    'transport',  # Admited to be backwards compatible, but not used. Will be removed on a future release.
    'force',
    'userIp',
    'user_ip',
)


# Enclosed methods under /tickets path
class Tickets(Handler):
    """
    Processes tickets access requests.
    Tickets are element used to "register" & "allow access" to users to a service.
    Designed to be used by external systems (like web services) to allow access to users to services.

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
       transport:  Ignored. Transport must be auto-detected on ticket auth
       force:  If "1" or "true" will ensure that:
                 - Groups exists on authenticator
                 - servicePool has these groups in it's allowed list
    """

    needs_admin = True  # By default, staff is lower level needed

    @staticmethod
    def result(result: str = '', error: typing.Optional[str] = None) -> dict[str, typing.Any]:
        """
        Returns a result for a Ticket request
        """
        res = {'result': result, 'date': datetime.datetime.now()}
        if error is not None:
            res['error'] = error
        return res

    def get(self) -> typing.Any:
        """
        Processes get requests, currently none
        """
        logger.debug('Ticket args for GET: %s', self._args)

        raise exceptions.rest.RequestError('Invalid request')

    def _check_parameters(self) -> None:
        # Parameters can only be theese
        for p in self._params:
            if p not in VALID_PARAMS:
                logger.debug('Parameter %s not in valid ticket parameters list', p)
                raise exceptions.rest.RequestError('Invalid parameters')

        if len(self._args) != 1 or self._args[0] not in ('create',):
            raise exceptions.rest.RequestError('Invalid method')

        try:
            for i in (
                'authId',
                'auth_id',
                'authTag',
                'auth_tag',
                'auth',
                'auth_name',
                'authSmallName',
            ):
                if i in self._params:
                    raise StopIteration

            if 'username' in self._params and 'groups' in self._params:
                raise StopIteration()

            raise exceptions.rest.RequestError('Invalid parameters (no auth or username/groups)')
        except StopIteration:
            pass  # All ok

    # Must be invoked as '/rest/ticket/create, with "username", ("authId" or "auth_id") or ("auth_tag" or "authSmallName" or "authTag"), "groups" (array) and optionally "time" (in seconds) as paramteres
    def put(
        self,
    ) -> dict[str, typing.Any]:
        """
        Processes put requests, currently only under "create"
        """
        logger.debug(self._args)

        # Check that call is correct (pamateters, args, ...)
        self._check_parameters()

        force: bool = self.get_param('force') in ('1', 'true', 'True', True)

        try:
            servicePoolId: typing.Optional[str] = None

            # First param is recommended, last ones are compatible with old versions
            authId = self.get_param('auth_id', 'authId')
            authName = self.get_param('auth_name', 'auth')
            authTag = self.get_param('auth_tag', 'authTag', 'authSmallName')

            # Will raise an exception if no auth found
            if authId:
                auth = models.Authenticator.objects.get(uuid=process_uuid(authId.lower()))
            elif authName:
                auth = models.Authenticator.objects.get(name=authName)
            else:
                auth = models.Authenticator.objects.get(small_name=authTag)

            username: str = self.get_param('username')
            password: str = self.get_param('password')
            # Some machines needs password, depending on configuration

            groupIds: list[str] = []
            for groupName in ensure.is_list(self.get_param('groups')):
                try:
                    groupIds.append(auth.groups.get(name=groupName).uuid or '')
                except Exception:
                    logger.info(
                        'Group %s from ticket does not exists on auth %s, forced creation: %s',
                        groupName,
                        auth,
                        force,
                    )
                    if force:  # Force creation by call
                        groupIds.append(
                            auth.groups.create(
                                name=groupName,
                                comments='Autocreated form ticket by using force paratemeter',
                            ).uuid
                            or ''
                        )

            if not groupIds:  # No valid group in groups names
                raise exceptions.rest.RequestError(
                    'Authenticator does not contain ANY of the requested groups and force is not used'
                )

            try:
                time = int(self.get_param('time') or 60)
                time = 60 if time < 1 else time
            except Exception:
                time = 60
            realname: str = self.get_param('realname', 'username') or ''

            poolUuid = self.get_param('servicePool')
            if poolUuid:
                # Check if is pool or metapool
                poolUuid = process_uuid(poolUuid)
                pool: typing.Union[models.ServicePool, models.MetaPool]

                try:
                    pool = models.MetaPool.objects.get(
                        uuid=poolUuid
                    )  # If not an metapool uuid, will process it as a servicePool
                    if force:
                        # First, add groups to metapool
                        for addGrp in set(groupIds) - set(pool.assignedGroups.values_list('uuid', flat=True)):
                            pool.assignedGroups.add(auth.groups.get(uuid=addGrp))
                        # And now, to ALL metapool members
                        for metaMember in pool.members.all():
                            # Now add groups to pools
                            for addGrp in set(groupIds) - set(
                                metaMember.pool.assignedGroups.values_list('uuid', flat=True)
                            ):
                                metaMember.pool.assignedGroups.add(auth.groups.get(uuid=addGrp))

                    # For metapool, transport is ignored..

                    servicePoolId = 'M' + pool.uuid
                except models.MetaPool.DoesNotExist:
                    pool = models.ServicePool.objects.get(uuid=poolUuid)

                    # If forced that servicePool must honor groups
                    if force:
                        for addGrp in set(groupIds) - set(pool.assignedGroups.values_list('uuid', flat=True)):
                            pool.assignedGroups.add(auth.groups.get(uuid=addGrp))

                    servicePoolId = 'F' + pool.uuid

        except models.Authenticator.DoesNotExist:
            return Tickets.result(error='Authenticator does not exists')
        except models.ServicePool.DoesNotExist:
            pass
            return Tickets.result(error='Service pool (or metapool) does not exists')
        except models.Transport.DoesNotExist:
            pass
            return Tickets.result(error='Transport does not exists')
        except Exception as e:
            return Tickets.result(error=str(e))

        data = {
            'username': username,
            'password': CryptoManager().encrypt(password),
            'realname': realname,
            'groups': groupIds,
            'auth': auth.uuid,
            'servicePool': servicePoolId,
        }

        ticket = models.TicketStore.create(data)

        return Tickets.result(ticket)
