# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.U.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

import typing
import logging

from django.utils.translation import ugettext_noop as _
from uds.core import Module
from uds.core.transports import protocols
from uds.core.util.state import State
from uds.core.util import log

from . import types
from .publication import Publication
from .user_deployment import UserDeployment

if typing.TYPE_CHECKING:
    from uds.core import services
    from uds.core import osmanagers
    from uds.core.environment import Environment
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
    (i.e. cacheTooltip, usesCache_L2 and cacheTooltip_L2)

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
    the class must be serialized and unserialized, because there is no warrantee that
    the object will get two methods invoked without haven't been removed from memory
    and loaded again. One thing to have into account on this are Form Fields, that
    default implementation marshals and unmashals them, so if your case is that you
    only need data that is keeped at form fields, marshal and unmarshal and in fact
    not needed.

    """

    # : Constant for indicating that max elements this service can deploy is unlimited.
    UNLIMITED: int = -1

    # : Name of type, used at administration interface to identify this
    # : service (i.e. Xen server, oVirt Server, ...)
    # : This string will be translated when provided to admin interface
    # : using ugettext, so you can mark it as "_" at derived classes (using ugettext_noop)
    # : if you want so it can be translated.
    typeName = _('Base Service')

    # : Name of type used by Managers to identify this type of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    typeType = 'BaseService'

    # : Description shown at administration level for this service.
    # : This string will be translated when provided to admin interface
    # : using ugettext, so you can mark it as "_" at derived classes (using ugettext_noop)
    # : if you want so it can be translated.
    typeDescription = _('Base Service')

    # : Icon file, used to represent this service at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own :py:meth:uds.core.module.BaseModule.icon method.
    iconFile = 'service.png'

    # Functional related data

    # : Normally set to UNLIMITED. This attribute indicates if the service has some "limitation"
    # : for providing deployed services to users. This attribute can be set here or
    # : modified at instance level, core will access always to it using an instance object.
    maxDeployed: int = UNLIMITED  # : If the service provides more than 1 "provided service" (-1 = no limit, 0 = ???? (do not use it!!!), N = max number to deploy

    # : If this item "has constains", on deployed service edition, defined keys will overwrite defined ones
    # : That is, this Dicionary will OVERWRITE fields ON ServicePool (normally cache related ones) dictionary from a REST api save invocation!!
    cacheConstrains: typing.Optional[typing.MutableMapping[str, typing.Any]] = None

    # : If this class uses cache or not. If uses cache is true, means that the
    # : service can "prepare" some user deployments to allow quicker user access
    # : to services if he already do not have one.
    # : If you set this to True, please, provide a _ :py:attr:.cacheToolTip
    usesCache = False

    # : Tooltip to be used if services uses cache at administration interface, indicated by :py:attr:.usesCache
    cacheTooltip = _('None')  # : Tooltip shown to user when this item is pointed at admin interface

    # : If user deployments can be cached (see :py:attr:.usesCache), may he also can provide a secondary cache,
    # : that is no more that user deployments that are "almost ready" to be used, but preperably consumes less
    # : resources than L1 cache. This can give a boost to cache L1 recovering in case of peaks
    # : in demand. If you set this to True, please, provide also  a _ :py:attr:.cacheTooltip_L2
    usesCache_L2 = False  # : If we need to generate a "Level 2" cache for this service (i.e., L1 could be running machines and L2 suspended machines)

    # : Tooltip to be used if services uses L2 cache at administration interface, indicated by :py:attr:.usesCache_L2
    cacheTooltip_L2 = _('None')  # : Tooltip shown to user when this item is pointed at admin interface

    # : If the service needs a o.s. manager (see os managers section)
    needsManager: bool = False

    # : If the service can be autoassigned or needs to be assigned by administrator
    # : Not all services are for assigning it. Thing, i.e., a Service that manages
    # : a number of Server. The desired behavior will be to let administrator
    # : the service to a user in the administration interface, an not the system
    # : to assign the service automatically. If this is true, the core will not
    # : assign the service automatically, so if the user do not have a consumable
    # : assigned, the user will never get one (of this kind, of course)
    mustAssignManually: typing.ClassVar[bool] = False

    # : Types of publications (preparated data for deploys)
    # : If you provide this, UDS will assume that the service needs a preparation.
    # : If not provided (it is None), UDS will assume that service do not needs
    # : preparation. Take care, if you mark a service as it uses cache, you MUST
    # : provide a publication type
    # : This refers to class that provides the logic for publication, you can see
    # : :py:class:uds.core.services.Publication
    publicationType: typing.ClassVar[typing.Optional[typing.Type[Publication]]] = None

    # : Types of deploys (services in cache and/or assigned to users)
    # : This is ALWAYS a MUST. You mast indicate the class responsible
    # : for managing the user deployments (user consumable services generated
    # : from this one). If this attribute is not set, the service will never work
    # : (core will not know how to handle the user deployments)
    deployedType: typing.ClassVar[typing.Optional[typing.Type[UserDeployment]]] = None

    # : Restricted transports
    # : If this list contains anything else but emtpy, the only allowed protocol for transports
    # : will be the ones listed here (on implementation, ofc)
    allowedProtocols: typing.Iterable = protocols.GENERIC

    # : If this services "spawns" a new copy on every execution (that is, does not "reuse" the previous opened session)
    # : Default behavior is False (and most common), but some services may need to respawn a new "copy" on every launch
    spawnsNew: bool = False

    # : If the service allows "reset", here we will announce it
    # : Defaults to False
    canReset = False

    # : 'kind' of services that this service provides:
    # : For example, VDI, VAPP, ...
    servicesTypeProvided: typing.Iterable = types.ALL

    _provider: 'services.ServiceProvider'

    def __init__(self, environment, parent: 'services.ServiceProvider', values: Module.ValuesType = None, uuid: typing.Optional[str] = None):
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

    def parent(self) -> 'services.ServiceProvider':
        """
        Utility method to access parent provider for this service

        Returns

            Parent provider instance object (not database object)
        """
        return self._provider

    def requestServicesForAssignation(self, **kwargs) -> typing.Iterable[UserDeployment]:
        """
        override this if mustAssignManualy is True
        @params kwargs: Named arguments
        @return an array with the services that we can assign (they must be of type deployedType)
        We will access the returned array in "name" basis. This means that the service will be assigned by "name", so be care that every single service
        returned are not repeated... :-)
        """
        raise Exception('The class {0} has been marked as manually asignable but no requestServicesForAssignetion provided!!!'.format(self.__class__.__name__))

    def macGenerator(self) -> typing.Optional['UniqueMacGenerator']:
        """
        Utility method to access provided macs generator (inside environment)

        Returns the environment unique mac addresses generator
        """
        return typing.cast('UniqueMacGenerator', self.idGenerators('mac'))

    def nameGenerator(self) -> typing.Optional['UniqueNameGenerator']:
        """
        Utility method to access provided names generator (inside environment)

        Returns the environment unique name generator
        """
        return typing.cast('UniqueNameGenerator', self.idGenerators('name'))

    def listAssignables(self) -> typing.Iterable[typing.Tuple[str, str]]:
        """
        If overrided, will provide list of assignables elements, so we can "add" an element manually to the list of assigned user services
        If not overriden, means that it cannot assign manually

        Returns:
            typing.List[typing.Tuple[str, str]] -- List of asignables services, first element is id, second is name of the element
        """
        return []

    def assignFromAssignables(self, assignableId: str, user: 'models.User', userDeployment: UserDeployment) -> str:
        """
        Assigns from it internal assignable list to an user

        Arguments:
            assignableId {str} -- [description]
            user {[type]} -- [description]
            userDeployment {UserDeployment} -- [description]

        Returns:
            str -- State
        """
        return State.FINISHED

    def getToken(self) -> typing.Optional[str]:
        """
        This method is to allow some kind of services to register a "token", so special actors
        (for example, those for static pool of machines) can communicate with UDS services for
        several actor.
        By default, services does not have a token
        """
        return None

    def getValidId(self, idsList: typing.Iterable[str]) -> typing.Optional[str]:
        """
        Looks for an "owned" id in the provided list. If found, returns it, else return None

        Args:
            idsList (typing.Iterable[str]): List of IPs and MACs that acts as 

        Returns:
            typing.Optional[str]: [description]
        """
        return None

    def processLogin(self, id: str, remote_login: bool) -> None:
        """
        In the case that a login is invoked directly on an actor controlled machine with
        an service token, this method will be called with provided info by uds actor (parameters)

        Args:
            id (str): Id validated through "getValidId"
            remote_login (bool): if the login seems to be a remote login
        """
        return

    def processLogout(self, id: str) -> None:
        """
        In the case that a login is invoked directly on an actor controlled machine with
        an service token, this method will be called with provided info by uds actor (parameters)

        Args:
            id (str): Id validated through "getValidId"
            remote_login (bool): if the login seems to be a remote login
        """
        return

    def notifyInitialization(self, id: str) -> None:
        """
        In the case that the startup of a "tokenized" method is invoked (unmanaged method of actor_v3 rest api),
        this method is forwarded, so the tokenized method could take proper actions on a "known-to-be-free service"      

        Args:
            id (str): Id validated through "getValidId"
        """

    def storeIdInfo(self, id: str, data: typing.Any) -> None:
        self.storage.putPickle('__nfo_' + id, data)

    def recoverIdInfo(self, id: str, delete: bool = False) -> typing.Any:
        # recovers the information
        value = self.storage.getPickle('__nfo_' + id)
        if value and delete:
            self.storage.delete('__nfo_' + id)
        return value


    def doLog(self, level: int, message: str) -> None:
        """
        Logs a message with requested level associated with this service
        """
        from uds.models import Service as DBService
        if self.getUuid():
            log.doLog(DBService.objects.get(uuid=self.getUuid()), level, message, log.SERVICE)

    @classmethod
    def canAssign(cls) -> bool:
        """
        Helper to query if a class is custom (implements getJavascript method)
        """
        return cls.listAssignables is not Service.listAssignables  and cls.assignFromAssignables is not Service.assignFromAssignables

    def __str__(self):
        """
        String method, mainly used for debugging purposes
        """
        return 'Base Service Provider'
