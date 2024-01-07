# pylint: disable=unused-argument  # this has a lot of "default" methods, so we need to ignore unused arguments most of the time

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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

from ast import If
import typing
import collections.abc
import logging

from django.utils.translation import gettext_noop as _
from uds.core.module import Module
from uds.core.ui.user_interface import gui
from uds.core.util.state import State
from uds.core.util import log

from uds.core import types, consts


if typing.TYPE_CHECKING:
    from .user_service import UserService
    from .publication import Publication
    from uds.core import services
    from uds.core.util.unique_name_generator import UniqueNameGenerator
    from uds.core.util.unique_mac_generator import UniqueMacGenerator
    from uds.core.util.unique_gid_generator import UniqueGIDGenerator
    from uds import models

logger = logging.getLogger(__name__)


class Service(Module):
    """
    This class is in fact an interface, and represents a service, that is the
    definition of an offering for consumers (users).

    Class derived from this one declares the behavior of the service, as well
    as custom parameter that will be needed to provide final consumable elements
    to users.

    The behavior attributes must be declared always, although they have default
    values, this can change in a future and declaring all needed is a good way
    to avoid future problems. Of course, if you declare that do no do something
    (i.e. do not uses cache), you will not have to declare related attributes
    (i.e. cache_tooltip, uses_cache_l2 and cache_tooltip_l2)

    As you derive from this class, if you provide __init__ in your own class,
    remember to call ALWAYS at base class __init__  as this:

       super().__init__(parent, environment, values)

    This is a MUST (if you override __init__), so internal structured gets
    filled correctly, so don't forget it!.

    The preferred method of provide initialization is to provide the :py:meth:`.initialize`,
    and do not override __init__ method. This (initialize) will be invoked after
    all internal initialization, so there will be available parent, environment and storage.

    Normally objects of classes deriving from this one, will be serialized, called,
    deserialized. This means that all that you want to ensure that is kept inside
    the class must be serialized and deserialized, because there is no warrantee that
    the object will get two methods invoked without haven't been removed from memory
    and loaded again. One thing to have into account on this are Form Fields, that
    default implementation marshals and unmashals them, so if your case is that you
    only need data that is keeped at form fields, marshal and unmarshal and in fact
    not needed.

    """

    # : Name of type, used at administration interface to identify this
    # : service (i.e. Xen server, oVirt Server, ...)
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_name = _('Base Service')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    type_type = 'BaseService'

    # : Description shown at administration level for this service.
    # : This string will be translated when provided to admin interface
    # : using gettext, so you can mark it as "_" at derived classes (using gettext_noop)
    # : if you want so it can be translated.
    type_description = _('Base Service')

    # : Icon file, used to represent this service at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    icon_file = 'service.png'

    # Functional related data

    # : Normally set to UNLIMITED. This attribute indicates if the service has some "limitation"
    # : for providing user services. This attribute can be set here or
    # : modified at instance level, core will access always to it using an instance object.
    # : Note: you can override this value on service instantiation by providing a "maxService":
    # :      - If maxServices is an integer, it will be used as max_user_services
    # :      - If maxServices is a gui.NumericField, it will be used as max_user_services (.num() will be called)
    # :      - If maxServices is a callable, it will be called and the result will be used as max_user_services
    # :      - If maxServices is None, max_user_services will be set to consts.UNLIMITED (as default)
    max_user_services: int = consts.UNLIMITED

    # : If this item "has overrided fields", on deployed service edition, defined keys will overwrite defined ones
    # : That is, this Dicionary will OVERWRITE fields ON ServicePool (normally cache related ones) dictionary from a REST api save invocation!!
    # : Example:
    # :    overrided_fields = {
    # :        'cache_l2_srvs': 10,
    # :        'cache_l1_srvs': 20,
    # :    }
    # : This means that service pool will have cache_l2_srvs = 10 and cache_l1_srvs = 20, no matter what the user has provided
    # : on a save invocation to REST api for ServicePool
    overrided_fields: typing.Optional[collections.abc.MutableMapping[str, typing.Any]] = None

    # : If this class uses cache or not. If uses cache is true, means that the
    # : service can "prepare" some user deployments to allow quicker user access
    # : to services if he already do not have one.
    # : If you set this to True, please, provide a _ :py:attr:.cacheToolTip
    uses_cache = False

    # : Tooltip to be used if services uses cache at administration interface, indicated by :py:attr:.uses_cache
    cache_tooltip = _('None')  # : Tooltip shown to user when this item is pointed at admin interface

    # : If user deployments can be cached (see :py:attr:.uses_cache), may he also can provide a secondary cache,
    # : that is no more that user deployments that are "almost ready" to be used, but preperably consumes less
    # : resources than L1 cache. This can give a boost to cache L1 recovering in case of peaks
    # : in demand. If you set this to True, please, provide also  a _ :py:attr:.cache_tooltip_l2
    uses_cache_l2 = False  # : If we need to generate a "Level 2" cache for this service (i.e., L1 could be running machines and L2 suspended machines)

    # : Tooltip to be used if services uses L2 cache at administration interface, indicated by :py:attr:.uses_cache_l2
    cache_tooltip_l2 = _('None')  # : Tooltip shown to user when this item is pointed at admin interface

    # : If the service needs a o.s. manager (see os managers section)
    needs_manager: bool = False

    # : If the service can be autoassigned or needs to be assigned by administrator
    # : Not all services are for assigning it. Thing, i.e., a Service that manages
    # : a number of Server. The desired behavior will be to let administrator
    # : the service to a user in the administration interface, an not the system
    # : to assign the service automatically. If this is true, the core will not
    # : assign the service automatically, so if the user do not have a consumable
    # : assigned, the user will never get one (of this kind, of course)
    must_assign_manually: typing.ClassVar[bool] = False

    # : Types of publications (preparated data for deploys)
    # : If you provide this, UDS will assume that the service needs a preparation.
    # : If not provided (it is None), UDS will assume that service do not needs
    # : preparation. Take care, if you mark a service as it uses cache, you MUST
    # : provide a publication type
    # : This refers to class that provides the logic for publication, you can see
    # : :py:class:uds.core.services.Publication
    publication_type: typing.ClassVar[typing.Optional[type['Publication']]] = None

    # : Types of deploys (services in cache and/or assigned to users)
    # : This is ALWAYS a MUST. You mast indicate the class responsible
    # : for managing the user deployments (user consumable services generated
    # : from this one). If this attribute is not set, the service will never work
    # : (core will not know how to handle the user deployments)
    user_service_type: typing.ClassVar[typing.Optional[type['UserService']]] = None

    # : Restricted transports
    # : If this list contains anything else but emtpy, the only allowed protocol for transports
    # : will be the ones listed here (on implementation, ofc)
    allowed_protocols: collections.abc.Iterable[types.transports.Protocol] = types.transports.Protocol.generic_vdi()

    # : If this services "spawns" a new copy on every execution (that is, does not "reuse" the previous opened session)
    # : Default behavior is False (and most common), but some services may need to respawn a new "copy" on every launch
    # This is a class attribute, so it can be overriden at instance level
    spawns_new: bool = False

    # : If the service allows "reset", here we will announce it
    # : Defaults to False
    can_reset = False

    # : 'kind' of services that this service provides:
    # : For example, VDI, VAPP, ...
    services_type_provided: types.services.ServiceType = types.services.ServiceType.VDI

    _provider: 'services.ServiceProvider'  # Parent instance (not database object)

    _db_obj: typing.Optional['models.Service'] = None  # Database object cache

    def __init__(
        self,
        environment,
        parent: 'services.ServiceProvider',
        values: Module.ValuesType = None,
        uuid: typing.Optional[str] = None,
    ):
        """
        Do not forget to invoke this in your derived class using "super().__init__(environment, parent, values)".
        We want to use the env, parent methods outside class. If not called, you must implement your own methods
        cache and storage are "convenient" methods to access _env.cache and _env.storage
        """
        Module.__init__(self, environment, values, uuid)
        self._provider = parent
        self.initialize(values)

    def initialize(self, values: Module.ValuesType) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            Values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        """

    def db_obj(self) -> 'models.Service':
        """
        Returns the database object associated with this service
        """
        from uds.models import Service

        if self._db_obj is None:
            self._db_obj = Service.objects.get(uuid=self.get_uuid())
        return self._db_obj

    def parent(self) -> 'services.ServiceProvider':
        """
        Utility method to access parent provider for this service

        Returns

            Parent provider instance object (not database object)
        """
        return self._provider

    def is_avaliable(self) -> bool:
        """
        Returns if this service is reachable (that is, we can operate with it). This is used, for example, to check
        if a service is "operable" before removing an user service (pass from "waiting for removal" to "removing")
        By default, this method returns True.
        Ideally, availability should be cached for a while, so that we don't have to check it every time.
        """
        return True

    def unmarshal(self, data: bytes) -> None:
        # In fact, we will not unmarshall anything here, but setup maxDeployed
        # if maxServices exists and it is a gui.NumericField
        # Invoke base unmarshall, so "gui fields" gets loaded from data
        super().unmarshal(data)

        if hasattr(self, 'maxServices'):
            # Fix self "max_user_services" value after loading fields
            try:
                maxServices = getattr(self, 'maxServices', None)
                if isinstance(maxServices, int):
                    self.max_user_services = maxServices
                elif isinstance(maxServices, gui.NumericField):
                    self.max_user_services = maxServices.num()
                    # For 0 values on max_user_services field, we will set it to UNLIMITED
                    if self.max_user_services == 0:
                        self.max_user_services = consts.UNLIMITED
                elif callable(maxServices):
                    self.max_user_services = maxServices()
                else:
                    self.max_user_services = consts.UNLIMITED
            except Exception:
                self.max_user_services = consts.UNLIMITED

            # Ensure that max_user_services is not negative
            if self.max_user_services < 0:
                self.max_user_services = consts.UNLIMITED

        # Keep untouched if maxServices is not present

    def user_services_for_assignation(self, **kwargs) -> collections.abc.Iterable['UserService']:
        """
        override this if mustAssignManualy is True
        @params kwargs: Named arguments
        @return an iterable with the services that we can assign  manually (they must be of type UserDeployment)
        We will access the returned iterable in "name" basis. This means that the service will be assigned by "name", so be care that every single service
        name returned is unique :-)
        """
        raise Exception(
            f'The class {self.__class__.__name__} has been marked as manually asignable but no requestServicesForAssignetion provided!!!'
        )

    def mac_generator(self) -> typing.Optional['UniqueMacGenerator']:
        """
        Utility method to access provided macs generator (inside environment)

        Returns the environment unique mac addresses generator
        """
        return typing.cast('UniqueMacGenerator', self.id_generators('mac'))

    def name_generator(self) -> typing.Optional['UniqueNameGenerator']:
        """
        Utility method to access provided names generator (inside environment)

        Returns the environment unique name generator
        """
        return typing.cast('UniqueNameGenerator', self.id_generators('name'))

    def enumerate_assignables(self) -> collections.abc.Iterable[tuple[str, str]]:
        """
        If overrided, will provide list of assignables elements, so we can "add" an element manually to the list of assigned user services
        If not overriden, means that it cannot assign manually

        Returns:
            list[tuple[str, str]] -- List of asignables services, first element is id, second is name of the element
        """
        return []

    def assign_from_assignables(
        self, assignableId: str, user: 'models.User', userDeployment: 'UserService'
    ) -> str:
        """
        Assigns from it internal assignable list to an user

        args:
            assignableId: Id of the assignable element
            user: User to assign to
            userDeployment: User deployment to assign

        Note:
            Base implementation does nothing, to be overriden if needed

        Returns:
            str: The state of the service after the assignation

        """
        return State.FINISHED

    def get_token(self) -> typing.Optional[str]:
        """
        This method is to allow some kind of services to register a "token", so special actors
        (for example, those for static pool of machines) can communicate with UDS services for
        several actor.
        By default, services does not have a token
        """
        return None

    def get_vapp_launcher(self, userService: 'models.UserService') -> typing.Optional[tuple[str, str]]:
        """Returns the vapp launcher for this service, if any

        Args:
            userService (UserService): User service to get the vapp launcher from

        Returns:
            typing.Optional[tuple[str, str]]: A tuple with the vapp launcher name and the vapp launcher path on server
        """
        return None

    def get_valid_id(self, idsList: collections.abc.Iterable[str]) -> typing.Optional[str]:
        """
        Looks for an "owned" id in the provided list. If found, returns it, else return None

        Args:
            idsList (collections.abc.Iterable[str]): List of IPs and MACs that acts as

        Returns:
            typing.Optional[str]: [description]
        """
        return None

    def process_login(self, id: str, remote_login: bool) -> None:
        """
        In the case that a login is invoked directly on an actor controlled machine with
        an service token, this method will be called with provided info by uds actor (parameters)
        That is, this method will only be called it UDS does not recognize the invoker, but the invoker
        has a valid token and the service has recognized it. (via getValidId)

        Args:
            id (str): Id validated through "getValidId"
            remote_login (bool): if the login seems to be a remote login
        """
        return

    def process_logout(self, id: str, remote_login: bool) -> None:
        """
        In the case that a logout is invoked directly on an actor controlled machine with
        an service token, this method will be called with provided info by uds actor (parameters)
        That is, this method will only be called it UDS does not recognize the invoker, but the invoker
        has a valid token and the service has recognized it. (via getValidId)

        Args:
            id (str): Id validated through "getValidId"
        """
        return

    def notify_initialization(self, id: str) -> None:
        """
        In the case that the startup of a "tokenized" method is invoked (unmanaged method of actor_v3 rest api),
        this method is forwarded, so the tokenized method could take proper actions on a "known-to-be-free service"

        Args:
            id (str): Id validated through "getValidId"
        """
        return

    def notify_data(self, id: typing.Optional[str], data: str) -> None:
        """
        Processes a custom data notification, that must be interpreted by the service itself.
        This allows "token actors" to communicate with service directly, what is needed for
        some kind of services (like LinuxApps)

        Args:
            id (typing.Optional[str]): Id validated through "getValidId". May be None if not validated (or not provided)
            data (str): Data to process
        """
        return

    def store_id_info(self, id: str, data: typing.Any) -> None:
        self.storage.putPickle('__nfo_' + id, data)

    def recover_id_info(self, id: str, delete: bool = False) -> typing.Any:
        # recovers the information
        value = self.storage.getPickle('__nfo_' + id)
        if value and delete:
            self.storage.delete('__nfo_' + id)
        return value

    def notify_preconnect(
        self, userService: 'models.UserService', info: 'types.connections.ConnectionData'
    ) -> bool:
        """
        Notifies preconnect to server, if this allows it

        Args:
            userService: User service to notify
            info: Connection data to notify

        Returns:
            True if notification was sent, False otherwise
        """
        return False

    def do_log(self, level: log.LogLevel, message: str) -> None:
        """
        Logs a message with requested level associated with this service
        """
        from uds.models import Service as DBService  # pylint: disable=import-outside-toplevel

        if self.get_uuid():
            log.log(DBService.objects.get(uuid=self.get_uuid()), level, message, log.LogSource.SERVICE)

    @classmethod
    def can_assign(cls) -> bool:
        """
        Helper to query if a class is assignable (can be assigned to an user manually)
        """
        return (
            cls.enumerate_assignables is not Service.enumerate_assignables
            and cls.assign_from_assignables is not Service.assign_from_assignables
        )

    def __str__(self):
        """
        String method, mainly used for debugging purposes
        """
        return 'Base Service Provider'
