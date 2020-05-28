# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
import logging
import typing

from uds.core import Module
from uds.core.environment import Environment

from uds.core.util import log
from uds.core.util.config import GlobalConfig
from uds.core.ui import gui

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import Service

logger = logging.getLogger(__name__)


class ServiceProvider(Module):
    """
    Base Service Provider Class.

    All classes that will represent a service provider will need to be derived
    from this class.

    The preferred way of using this class is by its alias name, provided
    at uds.core.services module, ServiceProvider.

    This is a very basic class, intended to be the root class of services.
    This means that services are childs of this class, declared at "offers" attribute.

    As you derive from this class, if you provide __init__ in your own class,
    remember to call ALWAYS at base class __init__  as this:

        super(...., self).__init__(environment, values)

    The preferred method of provide initialization is to provide the :py:meth:`.initialize`,
    and do not overrie __init__ method. This (initialize) will be invoked after
    all internal initialization.

    This is a MUST, so internal structured gets filled correctly, so don't forget it!.

    Normally objects of classes deriving from this one, will be serialized, called,
    deserialized. This means that all that you want to ensure that is keeped inside
    the class must be serialized and unserialized, because there is no warantee that
    the object will get two methods invoked without haven't been removed from memory
    and loaded again. One thing to have into account on this are Form Fields, that
    default implementation marshals and unmashals them, so if your case is that you
    only need data that is keeped at form fields, marshal and unmarshal and in fact
    not needed.
    """

    # : Services that we offers. Here is a list of service types (python types) that
    # : this class will provide. This types are the python clases, derived from
    # : Service, that are childs of this provider
    offers: typing.List[typing.Type['Service']] = []

    # : Name of type, used at administration interface to identify this
    # : provider (i.e. Xen server, oVirt Server, ...)
    # : This string will be translated when provided to admin interface
    # : using ugettext, so you can mark it as "translatable" at derived classes (using ugettext_noop)
    # : if you want so it can be translated.
    typeName = 'Base Provider'

    # : Name of type used by Managers to identify this tipe of service
    # : We could have used here the Class name, but we decided that the
    # : module implementator will be the one that will provide a name that
    # : will relation the class (type) and that name.
    typeType = 'BaseServiceProvider'

    # : Description shown at administration level for this provider.
    # : This string will be translated when provided to admin interface
    # : using ugettext, so you can mark it as "translatable" at derived classes (using ugettext_noop)
    # : if you want so it can be translated.
    typeDescription = 'Base Service Provider'

    # : Icon file, used to represent this provider at administration interface
    # : This file should be at same folder as this class is, except if you provide
    # : your own py:meth:`uds.core.module.BaseModule.icon` method.
    iconFile = 'provider.png'

    # : This defines the maximum number of concurrent services that should be in state "in preparation" for this provider
    # : Default is return the GlobalConfig value of GlobalConfig.MAX_PREPARING_SERVICES
    # : Note: this variable can be either a fixed value (integer, string) or a Gui text field (with a .value property)
    maxPreparingServices: typing.Any = None

    # : This defines the maximum number of concurrent services that should be in state "removing" for this provider
    # : Default is return the GlobalConfig value of GlobalConfig.MAX_REMOVING_SERVICES
    # : Note: this variable can be either a fixed value (integer, string) or a Gui text field (with a .value property)
    maxRemovingServices: typing.Any = None

    # : This defines if the limits (max.. vars) should be taken into accout or simply ignored
    # : Default is return the GlobalConfig value of GlobalConfig.IGNORE_LIMITS
    # : Note: this variable can be either a fixed value (integer, string) or a Gui text field (with a .value)
    ignoreLimits: typing.Any = None

    @classmethod
    def getServicesTypes(cls) -> typing.List[typing.Type['Service']]:
        """
        Returns what type of services this provider offers
        """
        return cls.offers

    @classmethod
    def getServiceByType(cls, typeName: str) -> typing.Optional[typing.Type['Service']]:
        """
        Tries to locate a child service which type corresponds with the
        one provided.
        Returns None if can't find one.

        :note: The type that this method looks for is not the class, but
               the typeType that Service has.
        """
        for _type in cls.offers:
            if _type.type() == typeName:
                return _type
        return None

    def __init__(self, environment: Environment, values: 'Module.ValuesType' = None, uuid: typing.Optional[str] = None):
        """
        Do not forget to invoke this in your derived class using "super(self.__class__, self).__init__(environment, values)"
        if you override this method. Better is to provide an "__initialize__" method, that will be invoked
        by __init__
        Values parameter is provided (are not None) when creating or modifying the service provider, so params check should ocur here and, if not
        valid, raise an "ValidationException" message
        """
        super().__init__(environment, values, uuid=uuid)
        self.initialize(values)

    def initialize(self, values: 'Module.ValuesType') -> None:
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

    def getMaxPreparingServices(self) -> int:
        val = self.maxPreparingServices
        if val is None:
            val = self.maxPreparingServices = GlobalConfig.MAX_PREPARING_SERVICES.getInt(force=True)  # Recover global an cache till restart

        retVal = int(getattr(val, 'value', val))
        return retVal if retVal > 0 else 1

    def getMaxRemovingServices(self) -> int:
        val = self.maxRemovingServices
        if val is None:
            val = self.maxRemovingServices = GlobalConfig.MAX_REMOVING_SERVICES.getInt(force=True)  # Recover global an cache till restart

        retVal = int(getattr(val, 'value', val))
        return retVal if retVal > 0 else 1

    def getIgnoreLimits(self) -> bool:
        val = self.ignoreLimits
        if val is None:
            val = self.ignoreLimits = GlobalConfig.IGNORE_LIMITS.getBool(force=True)  # Recover global an cache till restart

        val = getattr(val, 'value', val)
        return val is True or val == gui.TRUE

    def doLog(self, level: int, message: str) -> None:
        """
        Logs a message with requested level associated with this service
        """
        from uds.models import Provider as DBProvider
        if self.getUuid():
            log.doLog(DBProvider.objects.get(uuid=self.getUuid()), level, message, log.SERVICE)

    def __str__(self):
        """
        Basic implementation, mostly used for debuging and testing, never used
        at user or admin interfaces.
        """
        return 'Base Service Provider'
