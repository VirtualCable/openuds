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

from uds.core import types, consts
from uds.core.environment import Environment
from uds.core.util import log, properties
from uds.core.util.model import sql_now
from uds.core.types.states import State
from uds.models.service_pool import ServicePool
from uds.models.service_pool_publication import ServicePoolPublication
from uds.models.user import User
from uds.models.uuid_model import UUIDModel

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import osmanagers, services
    from uds.models import AccountUsage, OSManager, UserServiceSession

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class UserService(UUIDModel, properties.PropertiesMixin):
    """
    This is the base model for assigned user service and cached user services.
    This are the real assigned services to users. ServicePool is the container (the group) of this elements.
    """

    # The reference to deployed service is used to accelerate the queries for different methods, in fact its redundant cause we can access to the deployed service
    # through publication, but queries are much more simple
    deployed_service = models.ForeignKey(ServicePool, on_delete=models.CASCADE, related_name='userServices')
    # Althoug deployed_services has its publication, the user service is bound to a specific publication
    # so we need to store the publication id here (or the revision, but we need to store something)
    # storing the id simplifies the queries
    publication = models.ForeignKey(
        ServicePoolPublication,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='userServices',
    )

    unique_id = models.CharField(max_length=128, default='', db_index=True)  # User by agents to locate machine
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
    in_use_date = models.DateTimeField(default=consts.NEVER)
    cache_level = models.PositiveSmallIntegerField(
        db_index=True, default=0
    )  # Cache level must be 1 for L1 or 2 for L2, 0 if it is not cached service

    src_hostname = models.CharField(max_length=consts.system.MAX_DNS_NAME_LENGTH, default='')
    src_ip = models.CharField(
        max_length=consts.system.MAX_IPV6_LENGTH, default=''
    )  # Source IP of the user connecting to the service. Max length is 45 chars (ipv6)

    # "fake" declarations for type checking
    # objects: 'models.manager.Manager["UserService"]'
    sessions: 'models.manager.RelatedManager[UserServiceSession]'
    accounting: 'AccountUsage'

    _cached_instance: typing.Optional['services.UserService'] = None

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

    # Helper to allow new names
    @property
    def service_pool(self) -> 'ServicePool':
        return self.deployed_service

    # For properties
    def get_owner_id_and_type(self) -> tuple[str, str]:
        return self.uuid, 'userservice'

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
        return self.properties.get('destroy_after', False) in (
            'y',
            True,
        )  # Compare to str to keep compatibility with old values

    @destroy_after.setter
    def destroy_after(self, value: bool) -> None:
        """
        Sets the to_be_removed property
        """
        self.properties['destroy_after'] = value

    @destroy_after.deleter
    def destroy_after(self) -> None:
        """
        Removes the to_be_removed property
        """
        del self.properties['destroy_after']

    def get_environment(self) -> Environment:
        """
        Returns an environment valid for the record this object represents.

        In the case of the user, there is an instatiation of "generators".
        Right now, there is two generators provided to child instance objects, that are
        valid for generating unique names and unique macs. In a future, there could be more generators

        To access this generators, use the Envirnment class, and the keys 'name' and 'mac'.

        (see related classes uds.core.util.unique_name_generator and uds.core.util.unique_mac_generator)
        """
        return Environment.environment_for_table_record(
            self._meta.verbose_name or self._meta.model_name or '',
            self.id,
        )

    def get_instance(self) -> 'services.UserService':
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
        if self._cached_instance:
            return self._cached_instance

        # We get the service instance, publication instance and osmanager instance
        servicepool = self.deployed_service
        if not servicepool.service:
            raise Exception('Service not found')
        service_instance = servicepool.service.get_instance()
        if service_instance.needs_osmanager is False or not servicepool.osmanager:
            osmanager_instance = None
        else:
            osmanager_instance = servicepool.osmanager.get_instance()
        # We get active publication
        publication_instance = None
        try:  # We may have deleted publication...
            if self.publication is not None:
                publication_instance = self.publication.get_instance()
        except Exception:
            # The publication to which this item points to, does not exists
            self.publication = None
            logger.exception(
                'Got exception at get_instance of an userservice %s (seems that publication does not exists!)',
                self,
            )
        if service_instance.user_service_type is None:
            raise Exception(
                f'Class {service_instance.__class__.__name__} needs user_service_type but it is not defined!!!'
            )
        instance = service_instance.user_service_type(
            self.get_environment(),
            service=service_instance,
            publication=publication_instance,
            osmanager=osmanager_instance,
            uuid=self.uuid,
        )
        if self.data:
            try:
                instance.deserialize(self.data)

                # if needs upgrade, we will serialize it again to ensure its format is upgraded ASAP
                # Eventually, it will be upgraded anyway, but could take too much time (even years)...
                # This way, if we instantiate it, it will be upgraded
                if instance.needs_upgrade():
                    self.data = instance.serialize()
                    self.save(update_fields=['data'])
                    instance.mark_for_upgrade(False)

            except Exception:
                logger.exception(
                    'Error unserializing %s//%s : %s',
                    self.deployed_service.name,
                    self.uuid,
                    self.data,
                )
        # Store for future uses
        self._cached_instance = instance
        return instance

    def update_data(self, userservice_instance: 'services.UserService') -> None:
        """
        Updates the data field with the serialized :py:class:uds.core.services.UserDeployment

        Args:
            dsp: :py:class:uds.core.services.UserDeployment to serialize

        :note: This method SAVES the updated record, just updates the field
        """
        if not userservice_instance.is_dirty():
            logger.debug('Skipping update of user service %s, no changes', self)
            return  # Nothing to do
        self.data = userservice_instance.serialize()
        self.save(update_fields=['data'])

    def get_name(self) -> str:
        """
        Returns the name of the user deployed service
        """
        if self.friendly_name == '':
            si = self.get_instance()
            self.friendly_name = si.get_name()
            self.update_data(si)

        return self.friendly_name

    def get_unique_id(self) -> str:
        """
        Returns the unique id of the user deployed service
        """
        if self.unique_id == '':
            si = self.get_instance()
            self.unique_id = si.get_unique_id()
            self.update_data(si)
        return self.unique_id

    def store_value(self, name: str, value: str) -> None:
        """
        Stores a value inside custom storage

        Args:
            name: Name of the value to store
            value: Value of the value to store
        """
        # Store value as a property
        self.properties[name] = value

    def recover_value(self, name: str) -> str:
        """
        Recovers a value from custom storage

        Args:
            name: Name of values to recover

        Returns:
            Stored value, None if no value was stored
        """
        val = self.properties.get(name)

        # To transition between old store at storage table and new properties table
        # If value is found on property, use it, else, try to recover it from storage
        if val is None:
            val = typing.cast(str, self.get_environment().storage.read(name))
        return val or ''

    def set_connection_source(self, src: types.connections.ConnectionSource) -> None:
        """
        Notifies that the last access to this service was initiated from provided params

        Args:
            ip: Ip from where the connection was initiated
            hostname: Hostname from where the connection was initiated

        Returns:
            Nothing
        """
        self.src_ip = src.ip[: consts.system.MAX_IPV6_LENGTH]
        self.src_hostname = src.hostname[: consts.system.MAX_DNS_NAME_LENGTH]

        if len(src.ip) > consts.system.MAX_IPV6_LENGTH or len(src.hostname) > consts.system.MAX_DNS_NAME_LENGTH:
            logger.info(
                'Truncated connection source data to %s/%s',
                self.src_ip,
                self.src_hostname,
            )

        self.save(update_fields=['src_ip', 'src_hostname'])

    def get_connection_source(self) -> types.connections.ConnectionSource:
        """
        Returns stored connection source data (ip & hostname)

        Returns:
            An array of two elements, first is the ip & second is the hostname

        :note: If the transport did not notified this data, this may be "empty"
        """
        return types.connections.ConnectionSource(
            self.src_ip or '0.0.0.0',  # nosec: not a binding address
            self.src_hostname or 'unknown',
        )

    def get_osmanager(self) -> typing.Optional['OSManager']:
        return self.deployed_service.osmanager

    def get_osmanager_instance(self) -> typing.Optional['osmanagers.OSManager']:
        osmanager = self.get_osmanager()
        if osmanager:
            return osmanager.get_instance()
        return None

    def needs_osmanager(self) -> bool:
        """
        Returns True if this User Service needs an os manager (i.e. parent services pools is marked to use an os manager)
        """
        return bool(self.get_osmanager())

    def allow_putting_back_to_cache(self) -> bool:
        return self.deployed_service.service.get_instance().allow_putting_back_to_cache()

    def transforms_user_or_password_for_service(self) -> bool:
        """
        If the os manager changes the username or the password, this will return True
        """
        return self.deployed_service.transforms_user_or_password_for_service()

    def process_user_password(self, username: str, password: str) -> tuple[str, str]:
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

        Notes:
            This method MUST be invoked by transport before using credentials passed to getJavascript.
        """
        servicepool = self.deployed_service
        if not servicepool.service:
            raise Exception('Service not found')
        service_instance = servicepool.service.get_instance()
        if service_instance.needs_osmanager is False or not servicepool.osmanager:
            return (username, password)

        return servicepool.osmanager.get_instance().update_credentials(self, username, password)

    def set_state(self, state: str) -> None:
        """
        Updates the state of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        if state != self.state:
            self.state_date = sql_now()
            self.state = state
            self.save(update_fields=['state', 'state_date'])

    def update_state_date(self) -> None:
        self.state_date = sql_now()
        self.save(update_fields=['state_date'])

    def set_os_state(self, state: str) -> None:
        """
        Updates the os state (state of the os) of this object and, optionally, saves it

        Args:
            state: new State to store at record

            save: Defaults to true. If false, record will not be saved to db, just modified

        """
        if state != self.os_state:
            self.state_date = sql_now()
            self.os_state = state
            self.save(update_fields=['os_state', 'state_date'])

    def assign_to(self, user: typing.Optional[User]) -> None:
        """
        Assigns this user deployed service to an user.

        Args:
            user: User to assing to (db record)
        """
        self.cache_level = 0
        self.state_date = sql_now()
        self.user = user
        self.save(update_fields=['cache_level', 'state_date', 'user'])

    def set_in_use(self, in_use: bool) -> None:
        """
        Set the "in_use" flag for this user deployed service

        Args:
            state: State to set to the "in_use" flag of this record

        :note: If the state is Fase (set to not in use), a check for removal of this deployed service is launched.
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.userservice import UserServiceManager

        self.in_use = in_use
        self.in_use_date = sql_now()
        self.save(update_fields=['in_use', 'in_use_date'])

        if in_use:
            # Start accounting if needed
            self.start_accounting()
        else:
            # Stop accounting if needed
            self.stop_accounting()
            # And check if now is time to remove it
            # Note: this checker is for "old publications"
            UserServiceManager.manager().process_not_in_use_and_old_publication(self)

    def start_accounting(self) -> None:
        # 1.- If do not have any account associated, do nothing
        # 2.- If called but already accounting, do nothing
        # 3.- If called and not accounting, start accounting
        # accounting comes from AccountUsage, and is a OneToOneRelation with UserService
        if self.deployed_service.account is None or hasattr(self, 'accounting'):
            return

        self.deployed_service.account.start_accounting(self)

    def stop_accounting(self) -> None:
        # 1.- If do not have any accounter associated, do nothing
        # 2.- If called but not accounting, do nothing
        # 3.- If called and accounting, stop accounting
        if self.deployed_service.account is None or hasattr(self, 'accounting') is False:
            return

        self.deployed_service.account.stop_accounting(self)

    def start_session(self) -> str:
        """
        Starts a new session for this user deployed service.
        Returns the session id
        """
        session = self.sessions.create()
        return session.session_id

    def end_session(self, session_id: str) -> None:
        if session_id == '':
            # Close all sessions
            for session in self.sessions.all():
                session.close()
        else:
            # Close a specific session
            try:
                session = self.sessions.get(session_id=session_id)
                session.close()
            except Exception:  # Does not exists, log it and ignore it
                logger.warning('Session %s does not exists for user deployed service', self.id)

    def is_usable(self) -> bool:
        """
        Returns if this service is usable
        """
        return State.from_str(self.state).is_usable()

    def is_preparing(self) -> bool:
        """
        Returns if this service is in preparation (not ready to use, but in its way to be so...)
        """
        return State.from_str(self.state).is_preparing()

    def is_ready(self) -> bool:
        """
        Returns if this service is ready (not preparing or marked for removal)
        """
        from uds.core.managers.userservice import UserServiceManager

        # Call to isReady of the instance
        return UserServiceManager.manager().is_ready(self)

    def is_in_maintenance(self) -> bool:
        return self.deployed_service.is_in_maintenance()

    def release(self, immediate: bool = False) -> None:
        """
        Mark this user deployed service for removal.
        If from_logout is true, maybe the service can return to cache, else, it will be removed
        """
        # log backtrace calling this method
        # import traceback
        # logger.info('Removing user service %s', self)
        # logger.info('\n*  '.join(traceback.format_stack()))

        if immediate:
            self.set_state(State.REMOVED)
        else:
            self.set_state(State.REMOVABLE)

    def cancel(self) -> None:
        """
        Asks the UserServiceManager to cancel the current operation of this user deployed service.
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.userservice import UserServiceManager

        # Cancel is a "forced" operation, so they are not checked against limits
        UserServiceManager.manager().cancel(self)

    def remove_or_cancel(self) -> None:
        """
        Marks for removal or cancels it, depending on state
        """
        if self.is_usable():
            self.release()
        else:
            self.cancel()

    def release_or_cancel(self) -> None:
        """
        A much more convenient method name that "removeOrCancel" (i think :) )
        """
        self.remove_or_cancel()

    def move_to_level(self, cache_level: types.services.CacheLevel) -> None:
        """
        Moves cache items betwen levels, managed directly

        Args:
            cache_level: New cache level to put object in
        """
        # pylint: disable=import-outside-toplevel
        from uds.core.managers.userservice import UserServiceManager

        UserServiceManager.manager().move_to_level(self, cache_level)

    def set_comms_endpoint(self, comms_url: typing.Optional[str] = None) -> None:
        self.properties['comms_url'] = comms_url

    def get_comms_endpoint(
        self, path: typing.Optional[str] = None
    ) -> typing.Optional[str]:  # pylint: disable=unused-argument
        # path is not used, but to keep compat with Server "getCommUrl" method
        return self.properties.get('comms_url', None)

    def notify_preconnect(self) -> None:
        """
        Notifies preconnect to userservice.
        TODO: Currently not used
        """
        pass

    def log_ip(self, ip: typing.Optional[str] = None) -> None:
        self.properties['ip'] = ip

    def get_log_ip(self) -> str:
        return self.properties.get('ip') or '0.0.0.0'  # nosec: no binding address

    @property
    def actor_version(self) -> str:
        return self.properties.get('actor_version') or '0.0.0'

    @actor_version.setter
    def actor_version(self, version: str) -> None:
        self.properties['actor_version'] = version

    def is_publication_valid(self) -> bool:
        """
        Returns True if this user service does not needs an publication, or if this deployed service publication is the current one
        """
        return (
            self.deployed_service.service.get_type().publication_type is None
            or self.publication == self.deployed_service.active_publication()
        )

    # Utility for logging
    def log(self, message: str, level: types.log.LogLevel = types.log.LogLevel.INFO) -> None:
        log.log(self, level, message, types.log.LogSource.INTERNAL)

    def test_connectivity(self, host: str, port: 'str|int', timeout: int = 4) -> bool:
        return self.deployed_service.test_connectivity(host, port, timeout)

    def __str__(self) -> str:
        return (
            f'User service {self.name}, unique_id {self.unique_id},'
            f' cache_level {self.cache_level}, user {self.user},'
            f' name {self.friendly_name}, state {State.from_str(self.state).localized}:{State.from_str(self.os_state).localized}'
        )

    @staticmethod
    def pre_delete(sender: typing.Any, **kwargs: typing.Any) -> None:  # pylint: disable=unused-argument
        """
        Used to invoke the Service class "Destroy" before deleting it from database.

        The main purpuse of this hook is to call the "destroy" method of the object to delete and
        to clear related data of the object (environment data such as own storage, cache, etc...

        :note: If destroy raises an exception, the deletion is not taken.
        """
        to_delete: 'UserService' = kwargs['instance']
        # Clear environment
        to_delete.get_environment().clean_related_data()
        # Ensure all sessions are closed (invoke with '' to close all sessions)
        # In fact, sessions are going to be deleted also, but we give then
        # the oportunity to execute some code before deleting them
        to_delete.end_session('')

        # Clear related logs to this user service
        log.clear_logs(to_delete)

        logger.debug('Deleted user service %s', to_delete)


# Connects a pre deletion signal to Authenticator
signals.pre_delete.connect(UserService.pre_delete, sender=UserService)
# Connects the properties signals
properties.PropertiesMixin.setup_signals(UserService)
