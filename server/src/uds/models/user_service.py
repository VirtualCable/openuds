# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.db import models
from django.db.models import signals
from uds.core import types

from uds.core.environment import Environment
from uds.core.util import log, unique
from uds.core.util.state import State

from uds.models.uuid_model import UUIDModel
from uds.models.service_pool import ServicePool
from uds.models.service_pool_publication import ServicePoolPublication
from uds.models.user import User
from uds.core.util.model import getSqlDatetime
from uds.models.consts import NEVER, MAX_IPV6_LENGTH, MAX_DNS_NAME_LENGTH

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import osmanagers
    from uds.core import services
    from uds.models import (
        OSManager,
        UserServiceProperty,
        UserServiceSession,
        AccountUsage,
    )

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class UserService(UUIDModel):
    """
    This is the base model for assigned user service and cached user services.
    This are the real assigned services to users. ServicePool is the container (the group) of this elements.
    """

    # The reference to deployed service is used to accelerate the queries for different methods, in fact its redundant cause we can access to the deployed service
    # through publication, but queries are much more simple
    deployed_service: 'models.ForeignKey["ServicePool"]' = models.ForeignKey(
        ServicePool, on_delete=models.CASCADE, related_name='userServices'
    )
    # Althoug deployed_services has its publication, the user service is bound to a specific publication
    # so we need to store the publication id here (or the revision, but we need to store something)
    # storing the id simplifies the queries
    publication: 'models.ForeignKey[ServicePoolPublication | None]' = models.ForeignKey(
        ServicePoolPublication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='userServices',
    )

    unique_id = models.CharField(
        max_length=128, default='', db_index=True
    )  # User by agents to locate machine
    friendly_name = models.CharField(max_length=128, default='')
    # We need to keep separated two differents os states so service operations (move beween caches, recover service) do not affects os manager state
    state = models.CharField(
        max_length=1, default=State.PREPARING, db_index=True
    )  # We set index so filters at cache level executes faster
    os_state = models.CharField(
        max_length=1, default=State.PREPARING
    )  # The valid values for this field are PREPARE and USABLE
    state_date = models.DateTimeField(db_index=True)
    creation_date = models.DateTimeField(db_index=True)
    data = models.TextField(default='')
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='userServices',
        null=True,
        blank=True,
        default=None,
    )
    in_use = models.BooleanField(default=False)
    in_use_date = models.DateTimeField(default=NEVER)
    cache_level = models.PositiveSmallIntegerField(
        db_index=True, default=0
    )  # Cache level must be 1 for L1 or 2 for L2, 0 if it is not cached service

    src_hostname = models.CharField(max_length=MAX_DNS_NAME_LENGTH, default='')
    src_ip = models.CharField(
        max_length=MAX_IPV6_LENGTH, default=''
    )  # Source IP of the user connecting to the service. Max length is 45 chars (ipv6)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["UserService"]'
    properties: 'models.manager.RelatedManager[UserServiceProperty]'
    sessions: 'models.manager.RelatedManager[UserServiceSession]'
    accounting: 'AccountUsage'

    class Meta(UUIDModel.Meta):  # pylint: disable=too-few-public-methods
        """
        Meta class to declare default order and unique multiple field index
        """

        db_table = 'uds__user_service'
        ordering = ('creation_date',)
        app_label = 'uds'
        indexes = [
            models.Index(fields=['deployed_service', 'cache_level', 'state']),
        ]

    @property
    def name(self) -> str:
        """
        Simple accessor to deployed service name plus unique name
        """
        return f'{self.deployed_service.name}\\{self.friendly_name}'

    @property
    def destroy_after(self) -> bool:
        """
        Returns True if this service is to be removed
        """
        return self.getProperty('to_be_removed', 'n') == 'y'

    @destroy_after.setter
    def destroy_after(self, value: bool) -> None:
        """
        Sets the to_be_removed property
        """
        self.setProperty('destroy_after', 'y' if value else 'n')

    @destroy_after.deleter
    def destroy_after(self) -> None:
        """
        Removes the to_be_removed property
        """
        self.deleteProperty('destroy_after')

    def getEnvironment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents.

        In the case of the user, there is an instatiation of "generators".
        Right now, there is two generators provided to child instance objects, that are
        valid for generating unique names and unique macs. In a future, there could be more generators

        To access this generators, use the Envirnment class, and the keys 'name' and 'mac'.

        (see related classes uds.core.util.unique_name_generator and uds.core.util.unique_mac_generator)
        """
        return Environment.getEnvForTableElement(
            self._meta.verbose_name,  # type: ignore  # pylint: disable=no-member
            self.id,
            {
                'mac': unique.UniqueMacGenerator,
                'name': unique.UniqueNameGenerator,
                'id': unique.UniqueGIDGenerator,
            },
        )

    def getInstance(self) -> 'services.UserDeployment':
        """
        Instantiates the object this record contains. In this case, the instantiated object needs also
        the os manager and the publication, so we also instantiate those here.

        Every single record of UserService model, represents an object.

        Args:
           values (list): Values to pass to constructor. If no values are especified,
                          the object is instantiated empty and them de-serialized from stored data.

        Returns:
            The instance Instance of the class this provider represents

        Raises:
        """
        # We get the service instance, publication instance and osmanager instance
        servicePool = self.deployed_service
        if not servicePool.service:
            raise Exception('Service not found')
        serviceInstance = servicePool.service.getInstance()
        if serviceInstance.needsManager is False or not servicePool.osmanager:
            osmanagerInstance = None
        else:
            osmanagerInstance = servicePool.osmanager.getInstance()
        # We get active publication
        publicationInstance = None
        try:  # We may have deleted publication...
            if self.publication is not None:
                publicationInstance = self.publication.getInstance()
        except Exception:
            # The publication to witch this item points to, does not exists
            self.publication = None  # type: ignore
            logger.exception(
                'Got exception at getInstance of an userService %s (seems that publication does not exists!)',
                self,
            )
        if serviceInstance.deployedType is None:
            raise Exception(
                f'Class {serviceInstance.__class__.__name__} needs deployedType but it is not defined!!!'
            )
        us = serviceInstance.deployedType(
            self.getEnvironment(),
            service=serviceInstance,
            publication=publicationInstance,
            osmanager=osmanagerInstance,
            dbservice=self,
        )
        if self.data != '' and self.data is not None:
            try:
                us.deserialize(self.data)
            except Exception:
                logger.exception(
                    'Error unserializing %s//%s : %s',
                    self.deployed_service.name,
                    self.uuid,
                    self.data,
                )
        return us

    def updateData(self, userServiceInstance: 'services.UserDeployment'):
        """
        Updates the data field with the serialized :py:class:uds.core.services.UserDeployment

        Args:
            dsp: :py:class:uds.core.services.UserDeployment to serialize

        :note: This method SAVES the updated record, just updates the field
        """
        self.data = userServiceInstance.serialize()
        self.save(update_fields=['data'])

    def getName(self) -> str:
        """
        Returns the name of the user deployed service
        """
        if self.friendly_name == '':
            si = self.getInstance()
            self.friendly_name = si.getName()
            self.updateData(si)

        return self.friendly_name

    def getUniqueId(self) -> str:
        """
        Returns the unique id of the user deployed service
        """
        if self.unique_id == '':
            si = self.getInstance()
            self.unique_id = si.getUniqueId()
            self.updateData(si)
        return self.unique_id

    def storeValue(self, name: str, value: str) -> None:
        """
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        """
        # Store value as a property
        self.setProperty(name, value)

    def recoverValue(self, name: str) -> str:
        """
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        """
        val = self.getProperty(name)

        # To transition between old stor at storage table and new properties table
        # If value is found on property, use it, else, try to recover it from storage
        if val is None:
            val = typing.cast(str, self.getEnvironment().storage.get(name))
        return val

    def setConnectionSource(self, src: types.ConnectionSourceType) -> None:
        """
        Notifies that the last access to this service was initiated from provided params

        Args:
            ip: Ip from where the connection was initiated
            hostname: Hostname from where the connection was initiated

        Returns:
            Nothing
        """
        self.src_ip = src.ip[:MAX_IPV6_LENGTH]
        self.src_hostname = src.hostname[:MAX_DNS_NAME_LENGTH]

        if len(src.ip) > MAX_IPV6_LENGTH or len(src.hostname) > MAX_DNS_NAME_LENGTH:
            logger.info(
                'Truncated connection source data to %s/%s',
                self.src_ip,
                self.src_hostname,
            )

        self.save(update_fields=['src_ip', 'src_hostname'])

    def getConnectionSource(self) -> types.ConnectionSourceType:
        """
        Returns stored connection source data (ip & hostname)

        Returns:
            An array of two elements, first is the ip & second is the hostname

        :note: If the transport did not notified this data, this may be "empty"
        """
        return types.ConnectionSourceType(
            self.src_ip or '0.0.0.0',  # nosec: not a binding address
            self.src_hostname or 'unknown',
        )

    def getOsManager(self) -> typing.Optional['OSManager']:
        return self.deployed_service.osmanager

    def getOsManagerInstance(self) -> typing.Optional['osmanagers.OSManager']:
        osManager = self.getOsManager()
        if osManager:
            return osManager.getInstance()
        return None

    def needsOsManager(self) -> bool:
        """
        Returns True if this User Service needs an os manager (i.e. parent services pools is marked to use an os manager)
        """
        return bool(self.getOsManager())

    def transformsUserOrPasswordForService(self):
        """
        If the os manager changes the username or the password, this will return True
        """
        return self.deployed_service.transformsUserOrPasswordForService()

    def processUserPassword(
        self, username: str, password: str
    ) -> typing.Tuple[str, str]:
        """
        Before accessing a service by a transport, we can request
        the service to "transform" the username & password that the transport
        will use to connect to that service.

        This method is here so transport USE it before using the username/password
        provided by user or by own transport configuration.

        Args:
            username: the username that will be used to connect to service
            password: the password that will be used to connect to service

        Return:
            An array of two elements, first is transformed username, second is
            transformed password.

        :note: This method MUST be invoked by transport before using credentials passed to getJavascript.
        """
        servicePool = self.deployed_service
        if not servicePool.service:
            raise Exception('Service not found')
        serviceInstance = servicePool.service.getInstance()
        if serviceInstance.needsManager is False or not servicePool.osmanager:
            return (username, password)

        return servicePool.osmanager.getInstance().processUserPassword(
            self, username, password
        )

    def setState(self, state: str) -> None:
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        if state != self.state:
            self.state_date = getSqlDatetime()
            self.state = state
            self.save(update_fields=['state', 'state_date'])

    def setOsState(self, state: str) -> None:
        """
        Updates the os state (state of the os) of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        if state != self.os_state:
            self.state_date = getSqlDatetime()
            self.os_state = state
            self.save(update_fields=['os_state', 'state_date'])

    def assignToUser(self, user: typing.Optional[User]) -> None:
        """
        Assigns this user deployed service to an user.

        Args:
            user: User to assing to (db record)
        """
        self.cache_level = 0
        self.state_date = getSqlDatetime()
        self.user = user
        self.save(update_fields=['cache_level', 'state_date', 'user'])

    def setInUse(self, inUse: bool) -> None:
        """
        Set the "in_use" flag for this user deployed service

        Args:
            state: State to set to the "in_use" flag of this record

        :note: If the state is Fase (set to not in use), a check for removal of this deployed service is launched.
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.user_service import UserServiceManager

        self.in_use = inUse
        self.in_use_date = getSqlDatetime()
        self.save(update_fields=['in_use', 'in_use_date'])

        # Start/stop accounting
        if inUse:
            self.startUsageAccounting()
        else:
            self.stopUsageAccounting()

        if not inUse:  # Service released, check y we should mark it for removal
            # If our publication is not current, mark this for removal
            UserServiceManager().checkForRemoval(self)

    def startUsageAccounting(self) -> None:
        # 1.- If do not have any account associated, do nothing
        # 2.- If called but already accounting, do nothing
        # 3.- If called and not accounting, start accounting
        # accounting comes from AccountUsage, and is a OneToOneRelation with UserService
        if self.deployed_service.account is None or hasattr(self, 'accounting'):
            return

        self.deployed_service.account.startUsageAccounting(self)

    def stopUsageAccounting(self) -> None:
        # 1.- If do not have any accounter associated, do nothing
        # 2.- If called but not accounting, do nothing
        # 3.- If called and accounting, stop accounting
        if (
            self.deployed_service.account is None
            or hasattr(self, 'accounting') is False
        ):
            return

        self.deployed_service.account.stopUsageAccounting(self)

    def initSession(self) -> str:
        """
        Starts a new session for this user deployed service.
        Returns the session id
        """
        session = self.sessions.create()
        return session.session_id

    def closeSession(self, sessionId: str) -> None:
        if sessionId == '':
            # Close all sessions
            for session in self.sessions.all():
                session.close()
        else:
            # Close a specific session
            try:
                session = self.sessions.get(session_id=sessionId)
                session.close()
            except Exception:  # Does not exists, log it and ignore it
                logger.warning(
                    'Session %s does not exists for user deployed service', self.id
                )

    def isUsable(self) -> bool:
        """
        Returns if this service is usable
        """
        return State.isUsable(self.state)

    def isPreparing(self) -> bool:
        """
        Returns if this service is in preparation (not ready to use, but in its way to be so...)
        """
        return State.isPreparing(self.state)

    def isReady(self) -> bool:
        """
        Returns if this service is ready (not preparing or marked for removal)
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.user_service import UserServiceManager

        # Call to isReady of the instance
        return UserServiceManager().isReady(self)

    def isInMaintenance(self) -> bool:
        return self.deployed_service.isInMaintenance()

    def remove(self) -> None:
        """
        Mark this user deployed service for removal
        """
        self.setState(State.REMOVABLE)

    def release(self) -> None:
        """
        A much more convenient method name that "remove" (i think :) )
        """
        self.remove()

    def cancel(self) -> None:
        """
        Asks the UserServiceManager to cancel the current operation of this user deployed service.
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.user_service import UserServiceManager

        UserServiceManager().cancel(self)

    def removeOrCancel(self) -> None:
        """
        Marks for removal or cancels it, depending on state
        """
        if self.isUsable():
            self.remove()
        else:
            self.cancel()

    def releaseOrCancel(self) -> None:
        """
        A much more convenient method name that "removeOrCancel" (i think :) )
        """
        self.removeOrCancel()

    def moveToLevel(self, cacheLevel: int) -> None:
        """
        Moves cache items betwen levels, managed directly

        Args:
            cacheLevel: New cache level to put object in
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.user_service import UserServiceManager

        UserServiceManager().moveToLevel(self, cacheLevel)

    def getProperty(
        self, propName: str, default: typing.Optional[str] = None
    ) -> typing.Optional[str]:
        try:
            val = self.properties.get(name=propName).value
            return val or default  # Empty string is null
        except Exception:
            return default

    def getProperties(self) -> typing.Dict[str, str]:
        """
        Retrieves all properties as a dictionary
        The number of properties per item is expected to be "relatively small" (no more than 5 items?)
        """
        dct: typing.Dict[str, str] = {}
        v: 'UserServiceProperty'
        for v in self.properties.all():
            dct[v.name] = v.value
        return dct

    def setProperty(
        self, propName: str, propValue: typing.Optional[str] = None
    ) -> None:
        prop, _ = self.properties.get_or_create(name=propName)
        prop.value = propValue or ''
        prop.save()

    def deleteProperty(self, propName: str) -> None:
        try:
            self.properties.get(name=propName).delete()
        except Exception:  # nosec: we don't care if it does not exists
            pass

    def setCommsUrl(self, commsUrl: typing.Optional[str] = None) -> None:
        self.setProperty('comms_url', commsUrl)

    def getCommsUrl(self) -> typing.Optional[str]:
        return self.getProperty('comms_url', None)

    def logIP(self, ip: typing.Optional[str] = None) -> None:
        self.setProperty('ip', ip)

    def getLoggedIP(self) -> str:
        return self.getProperty('ip') or '0.0.0.0'  # nosec: no binding address
    
    def setActorVersion(self, version: typing.Optional[str] = None) -> None:
        self.setProperty('actor_version', version)

    def getActorVersion(self) -> str:
        return self.getProperty('actor_version') or '0.0.0'

    def isValidPublication(self) -> bool:
        """
        Returns True if this user service does not needs an publication, or if this deployed service publication is the current one
        """
        return (
            self.deployed_service.service
            and self.deployed_service.service.getType().publicationType is None
        ) or self.publication == self.deployed_service.activePublication()

    # Utility for logging
    def log(self, message: str, level: log.LogLevel = log.LogLevel.INFO) -> None:
        log.doLog(self, level, message, log.LogSource.INTERNAL)

    def testServer(self, host, port, timeout=4) -> bool:
        return self.deployed_service.testServer(host, port, timeout)

    def __str__(self):
        return (
            f'User service {self.name}, unique_id {self.unique_id},'
            f' cache_level {self.cache_level}, user {self.user},'
            f' name {self.friendly_name}, state {State.toString(self.state)}:{State.toString(self.os_state)}'
        )

    @staticmethod
    def beforeDelete(sender, **kwargs) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        toDelete: 'UserService' = kwargs['instance']
        # Clear environment
        toDelete.getEnvironment().clearRelatedData()
        # Ensure all sessions are closed (invoke with '' to close all sessions)
        # In fact, sessions are going to be deleted also, but we give then
        # the oportunity to execute some code before deleting them
        toDelete.closeSession('')

        # Clear related logs to this user service
        log.clearLogs(toDelete)

        logger.debug('Deleted user service %s', toDelete)


# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(UserService.beforeDelete, sender=UserService)
