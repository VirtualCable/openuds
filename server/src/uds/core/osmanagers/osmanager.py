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
Author: Alexander Burmatov,  thatman at altlinux dot org
"""
import typing

from django.utils.translation import gettext_noop as _

from uds.core import types
from uds.core.types.states import State
from uds.core.util.stats.events import add_event
from uds.core.util import log
from uds.core.util.config import GlobalConfig
from uds.core.module import Module

STORAGE_KEY = 'osmk'

if typing.TYPE_CHECKING:
    from uds import models
    from uds.core.environment import Environment


class OSManager(Module):
    """
    An OS Manager is responsible for communication the service the different actions to take (i.e. adding a windows machine to a domain)
    The Service (i.e. virtual machine) communicates with the OSManager via a published web method, that must include the unique ID.
    In order to make easier to agents identify themselfs, the Unique ID can be a list with various Ids (i.e. the macs of the virtual machine).
    Server will iterate thought them and look for an identifier associated with the service. This list is a comma separated values (i.e. AA:BB:CC:DD:EE:FF,00:11:22:...)
    Remember also that we inherit the test and check methods from BaseModule
    """

    # Service informational related data
    type_name = _('Base OS Manager')
    type_type = 'osmanager'
    type_description = _('Base Manager')
    icon_file = 'osmanager.png'

    # : Type of services for which this OS Manager is designed
    # : Defaults to all. (list or tuple)
    services_types: typing.ClassVar[types.services.ServiceType] = types.services.ServiceType.VDI

    _db_obj: typing.Optional['models.OSManager'] = None

    def __init__(self, environment: 'Environment', values: types.core.ValuesType = None):
        super().__init__(environment, values)
        self.initialize(values)

    def initialize(self, values: types.core.ValuesType) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """
        pass

    def release(self, userservice: 'models.UserService') -> None:
        """
        Called by a service that is in Usable state before destroying it so osmanager can release data associated with it
        Only invoked for services that reach the state "removed"
        @return nothing
        """
        pass

    def db_obj(self) -> 'models.OSManager':
        """
        Returns the database object for this provider
        """
        from uds.models.osmanager import OSManager

        if self._db_obj is None:
            if not self.get_uuid():
                return OSManager.null()
            self._db_obj = OSManager.objects.get(uuid__iexact=self.get_uuid())

        return self._db_obj

    # These methods must be overriden
    def actor_data(
        self, userservice: 'models.UserService'  # pylint: disable=unused-argument
    ) -> types.osmanagers.ActorData:
        """
        This method provides information to actor, so actor can complete os configuration.
        Currently exists 3 types of os managers actions
        * rename vm and do NOT ADD to AD
          {
              'action': 'rename',
              'name': 'xxxxxx'
          }
        * rename vm and ADD to AD
          {
              'action': 'rename_ad',
              'name': 'xxxxxxx',
              'custom': # Dictionary with custom data for the os manager, currently only for ad join domain and random password
               {
                    'ad': 'domain.xxx'
                    'ou': 'ou'   # or '' if default ou
                    'username': 'userwithaddmachineperms@domain.xxxx'
                    'password': 'passwordForTheUserWithPerms',
                    'clientSoftware': 'sssd' or 'winbind' or 'automatically' if linux os manager,
                    'serverSoftware': 'active-directory' or 'ipa' if linux os manager,
                    'membershipSoftware': 'samba' or 'adcli' or 'automatically' if linux os manager,
                    'ssl': 'n' or 'y' if linux os manager,
                    'automaticIdMapping': 'n' or 'y' if linux os manager,
                    'isPersistent': 'n' or 'y' if linux os manager,
               }
          }
        * rename vm, do NOT ADD to AD, and change password for an user
          {
              'action': 'rename'
              'name': 'xxxxx'
              'custom':
              {
                 'username': 'username to change pass'
                 'password': 'current password for username to change password'
                 'new_password': 'new password to be set for the username'
              }
          }
        """
        return types.osmanagers.ActorData.null()

    def check_state(
        self, userservice: 'models.UserService'
    ) -> types.states.State:  # pylint: disable=unused-argument
        """
        This method must be overriden so your os manager can respond to requests from system to the current state of the service
        This method will be invoked when:
          * After service creation has finished, with the service wanting to see if it has to wait for os manager process finalization
          * Before assigning a service to an user (maybe this is not needed)?
          Notice that the service could be in any state. In fact, what we want with this is return FINISHED if nothing is expected from os o RUNING else
          The state will be updated by actors inside oss, so no more direct checking is needed
          @return: RUNNING, FINISHED
          We do not expect any exception from this method
        """
        return State.FINISHED

    # If true, this os manager  will be invoked with every user service assigned, but not used
    def manages_unused_userservices(self) -> bool:
        return False

    def handle_unused(self, userservice: 'models.UserService') -> None:
        """
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        """
        pass

    def is_removable_on_logout(self, userservice: 'models.UserService') -> bool:
        """
        If returns true, when actor notifies "logout", UDS will mark service for removal
        can be overriden
        """
        return True

    def max_idle(self) -> typing.Optional[int]:
        """
        If os manager request "max idle", this method will return a value different to None so actors will get informed on Connection
        @return Must return None (default if not override), or a "max idle" in seconds
        """
        return None

    def ignore_deadline(self) -> bool:
        return False

    @classmethod
    def is_credentials_modified_for_service(cls: type['OSManager']) -> bool:
        """
        Helper method that informs if the os manager transforms the username and/or the password.
        This is used from ServicePool
        """
        return cls.update_credentials != OSManager.update_credentials

    def update_credentials(
        self,
        userservice: 'models.UserService',  # pylint: disable=unused-argument
        username: str,
        password: str,
    ) -> tuple[str, str]:
        """
        This will be invoked prior to passsing username/password to Transport.

        This method allows us to "change" username and/or password "on the fly".
        One example of use of this is an OS Manager that creates a random password for an user.
        In that case, this method, if the username passed in is the same as the os manager changes the password for, return the changed password.

        MUST Return:
            An array with 2 elements, [newUserName, newPassword].
            Default method simply does nothing with in parameters, just returns it. (So, if your os manager does not need this,
            simply do not implement it)

        Note: This method is, right now, invoked by Transports directly. So if you implement a Transport, remember to invoke this
        """
        return username, password

    def destroy(self) -> None:
        """
        Invoked when OS Manager is deleted
        """

    def log_known_ip(self, userservice: 'models.UserService', ip: str) -> None:
        userservice.log_ip(ip)

    # Final method
    @typing.final
    def process_ready(self, userservice: 'models.UserService') -> None:
        '''
        Resets login counter to 0
        '''
        userservice.properties['logins_counter'] = 0
        # And execute ready notification method
        self.on_ready(userservice)

    @staticmethod
    def logged_in(userservice: 'models.UserService', username: typing.Optional[str] = None) -> None:
        """
        This method:
          - Add log in event to stats
          - Sets service in use
          - Invokes user_logged_in for user service instance
        """
        unique_id = userservice.unique_id
        userservice.set_in_use(True)
        userservice.properties['last_username'] = username or 'unknown'  # Store it for convenience
        userservice_instance = userservice.get_instance()
        userservice_instance.user_logged_in(username or 'unknown')
        userservice.update_data(userservice_instance)

        userservice_ip = userservice_instance.get_ip()

        full_username = userservice.user.pretty_name if userservice.user else 'unknown'

        know_user_ip = userservice.src_ip + ':' + userservice.src_hostname
        know_user_ip = know_user_ip if know_user_ip != ':' else 'unknown'

        username = username or 'unknown'

        add_event(
            userservice.service_pool,
            types.stats.EventType.LOGIN,
            fld1=username,
            fld2=know_user_ip,
            fld3=userservice_ip,
            fld4=full_username,
        )

        log.log(
            userservice,
            types.log.LogLevel.INFO,
            f'User {username} has logged in',
            types.log.LogSource.OSMANAGER,
        )

        log.log_use(
            'login',
            unique_id,
            userservice_ip,
            username,
            know_user_ip,
            full_username,
            userservice.friendly_name,
            userservice.deployed_service.name,
        )

        # Context makes a transaction, so we can use it to update the counter
        with userservice.properties as p:
            counter = int(typing.cast(str, p.get('logins_counter', 0))) + 1
            p['logins_counter'] = counter

    @staticmethod
    def logged_out(userservice: 'models.UserService', username: typing.Optional[str] = None) -> None:
        """
        This method:
          - Add log in event to stats
          - Sets service in use
        """
        with userservice.properties as p:
            counter = int(typing.cast(str, p.get('logins_counter', 0))) - 1
            if counter > 0:
                counter -= 1
            p['logins_counter'] = counter

        if GlobalConfig.EXCLUSIVE_LOGOUT.as_bool(True) and counter > 0:
            return

        unique_id = userservice.unique_id
        userservice.set_in_use(False)
        user_service_instance = userservice.get_instance()
        user_service_instance.user_logged_out(username or 'unknown')
        userservice.update_data(user_service_instance)

        service_ip = user_service_instance.get_ip()

        full_username = userservice.user.pretty_name if userservice.user else 'unknown'

        known_user_ip = userservice.src_ip + ':' + userservice.src_hostname
        known_user_ip = known_user_ip if known_user_ip != ':' else 'unknown'

        username = username or 'unknown'

        add_event(
            userservice.deployed_service,
            types.stats.EventType.LOGOUT,
            fld1=username,
            fld2=known_user_ip,
            fld3=service_ip,
            fld4=full_username,
        )

        log.log(
            userservice,
            types.log.LogLevel.INFO,
            f'User {username} has logged out',
            types.log.LogSource.OSMANAGER,
        )

        log.log_use(
            'logout',
            unique_id,
            service_ip,
            username,
            known_user_ip,
            full_username,
            userservice.friendly_name,
            userservice.deployed_service.name,
        )

    def on_ready(self, userservice: 'models.UserService') -> None:
        """
        Invoked by actor when userService is ready
        """

    def is_persistent(self) -> bool:
        """
        When a publication if finished, old assigned machines will be removed if this value is True.
        Defaults to False
        """
        return False

    def __str__(self) -> str:
        return "Base OS Manager"
