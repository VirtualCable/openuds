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
import typing

from uds.core import Environmentable
from uds.core import Serializable
from uds.core.util.state import State
from uds.core.util import log

if typing.TYPE_CHECKING:
    from uds import models
    from uds.core import services
    from uds.core import osmanagers
    from uds.core.environment import Environment
    from uds.core.util.unique_name_generator import UniqueNameGenerator
    from uds.core.util.unique_mac_generator import UniqueMacGenerator
    from uds.core.util.unique_gid_generator import UniqueGIDGenerator

class UserDeployment(Environmentable, Serializable):  # pylint: disable=too-many-public-methods
    """
    Interface for deployed services.

    This class provides the needed logic for implementing an "consumable user service",
    that are the elements that the user will interact with.

    A good way to understand this class is to look at the sample services provided
    with the documentation.

    As with all modules interfaces, if you override __init__ method,
    do not forget to invoke this class __init__  method as this::

       super(self.__class__, self).__init__(environment, **kwargs)

    This is a MUST (if you override __init___), so internal structured gets filled correctly, so don't forget it!.

    The preferred way of initializing, is to provide :py:meth:`.initialize`, that
    will be invoked just after all initialization stuff is done at __init__.

    Normally objects of classes deriving from this one, will be serialized, called,
    deserialized. This means that all that you want to ensure that is keeped inside
    the class must be serialized and unserialized, because there is no warantee that
    the object will get two methods invoked without haven't been remoded from memory
    and loaded again, this means, IMPLEMENT marshal and unmarshal with all attributes
    that you want to keep.


    Things to know about this class:

      * Once a deployment is done, it will never be called again for same instance
        object
      * The method getUniqueId will be invoked after call to deploys and check.
        You can change it on the fly, but remember that uniqueId is the "keyword"
        used inside services to communicate with os managers (os manager will
        receive an instance of UserDeployment, and this will be located via that
        uniqueId)

        Uniques ids can be repeated at database level, to let it come at a later
        deployment stage, but if two services has same uniqueid at a time,
        os manager will simply not work.
      * suggestedTime is always accessed through instance objects, and used after
        deployForCache, deployForUser and moveToCache it these methods returns
        RUNNING
      * Checks (if a deployment has finished, or the cache movement is finished)
        are always done using checkState(). It is secuential, i mean, will only
        be called when a deployment,a cache movement or a cancel operation is
        running
      * If the service that supports this deployeds do not use L2 cache, the
        moveCache method will never be invoked
      * The L1 cache should be a fast access cache (i.e. running service but
        not assigned to an user), while L2 cache should be non consuming or
        almost-non-consuming service. This means that if we cannont make an
        slower an less resources consumable form for a service, this should
        not have an L2 cache (slower is not a must,
        but probably it will be slower to recover from L2 cache than from L1,
        but faster than creating a new service)
        Ofc, if a service has an "Instant" creation, it don't needs cache...
      * We do not expect any exception from these methods, but if there is an
        error, the method can return "ERROR". To show the reason of error, the
        method reasonOfError can be called multiple times, including
        serializations in middle, so remember to include reason of error in serializations
    """
    L1_CACHE = 1  # : Constant for Cache of level 1
    L2_CACHE = 2  # : Constant for Cache of level 2

    # : Suggested time for deployment finishing, in seconds
    # : This allows the manager to, if deployment is no done in 1 step, re-check
    # : the deployment once this time has passed, i.e. KVM COW deployment takes
    # : low time, so we suggest to check at short intervals, but full copys takes
    # : a bit more so we can use longer interval checks
    # : This attribute is accessed always through an instance object,
    # : so u can modify it at your own implementation.
    suggestedTime = 10

    _service: 'services.Service'
    _publication: typing.Optional['services.Publication']
    _osmanager: typing.Optional['osmanagers.OSManager']
    _dbService: typing.Optional['models.UserService']
    _uuid: str

    def __init__(self, environment: 'Environment', **kwargs):
        """
        Do not forget to invoke this in your derived class using "super(self.__class__, self).__init__(environment, **kwargs)"
        We want to use the env, service and storage methods outside class. If not called, you must implement your own methods
        service and storage are "convenient" methods to access _env.service() and _env.storage

        Invoking this from derived classes is a MUST, again, do not forget it or your
        module will probable never work.

        Args:

            environment: Environment assigned to this publication
            kwargs: List of arguments that will receive:
                service: Parent service (derived from Service) of this deployment (this is an instance, not database object)
                publication: Parent publication (derived from Publication) of this deployment (optional)(this is an instance, not database object)
                osmanager: Parent osmanager (derived from :py:class:`uds.core.osmanagersOSManager`) of this deployment (optional)(this is an instance, not database object)
                dbservice: Database object for this service
        """
        Environmentable.__init__(self, environment)
        Serializable.__init__(self)
        self._service = kwargs['service']  # Raises an exception if service is not included. Parent
        self._publication = kwargs.get('publication', None)
        self._osmanager = kwargs.get('osmanager', None)
        self._dbService = kwargs.get('dbservice', None)
        self._uuid = kwargs.get('uuid', '')
        # If it has dbService, got uuid from it
        if self._dbService:
            self._uuid = self._dbService.uuid

        self.initialize()

    def initialize(self) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base class __init__.
        This will get invoked when all initialization stuff is done, so
        you can here access publication, service, osManager, ...
        """

    def getName(self) -> str:
        """
        Override this to return a name to display under some circustances

        Returns:

            name, default implementation returns unique id
        """
        return self.getUniqueId()

    def service(self) -> 'services.Service':
        """
        Utility method to access parent service. This doesn't need to be override.

        Normaly user deployments will need parent service to provide the
        consumable to the user.

        Returns:

            Parent service of this User Deployment
        """
        return self._service

    def publication(self) -> typing.Optional['services.Publication']:
        """
        Utility method to access publication. This doesn't need to be overriden.

        Returns:

            publication for this user deployment, or None if this deployment has
            no publication at all.
        """
        return self._publication

    def osmanager(self) -> typing.Optional['osmanagers.OSManager']:
        """
        Utility method to access os manager. This doesn't need to be overriden.

        Returns:

            os manager for this user deployment, or None if this deployment has
            no os manager.
        """
        return self._osmanager

    def getUuid(self) -> str:
        return self._uuid

    def dbservice(self) -> typing.Optional['models.UserService']:
        """
        Utility method to access database object for the object this represents.

        Returns:

            Database object that got unserialized to obtain this object.
        """
        return self._dbService

    def doLog(self, level: int, message: str) -> None:
        """
        Logs a message with requested level associated with this user deployment
        """
        log.doLog(self._dbService, level, message, log.SERVICE)

    def macGenerator(self) -> 'UniqueMacGenerator':
        """
        Utility method to access provided macs generator (inside environment)

        Returns the environment unique mac addresses generator
        """
        return typing.cast('UniqueMacGenerator', self.idGenerators('mac'))

    def nameGenerator(self) -> 'UniqueNameGenerator':
        """
        Utility method to access provided names generator (inside environment)

        Returns the environment unique name generator
        """
        return typing.cast('UniqueNameGenerator', self.idGenerators('name'))

    def gidGenerator(self) -> 'UniqueGIDGenerator':
        """
        Utility method to access provided names generator (inside environment)

        Returns the environment unique global id generator
        """
        return typing.cast('UniqueGIDGenerator', self.idGenerators('id'))

    def getUniqueId(self) -> str:
        """
        Obtains an unique id for this deployed service, you MUST override this

        Returns:

            An unique identifier for this object, that is an string and must be
            unique.
        """
        raise NotImplementedError('Base getUniqueId for User Deployment called!!!')

    def notifyReadyFromOsManager(self, data: typing.Any) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This method provides a mechanism to let os managers notify readyness
        to deployed services.

        Args:

            data: Data sent by os manager.
            Data is os manager dependant, so check if this data is known by you
            (normally, it will be None, but is os manager dependad as i say)

        This is a task-initiating method, so if there is something to do,
        just return State.RUNNING. If not, return State.FINISHED. In case of
        error, return State.ERROR and be ready to provide error message when

        if State.RUNNING is returned, the :py:meth:.checkState method will be
        used to check when this process has finished.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        return State.FINISHED

    def getIp(self) -> str:
        """
        All services are "IP" services, so this method is a MUST

        Returns:

            The needed ip to let the user connect to the his deployed service.
            This ip will be managed by transports, without IP there is no connection
        """
        raise Exception('Base getIp for User Deployment got called!!!')

    def setIp(self, ip: str) -> None:
        """
        This is an utility method, invoked by some os manager to notify what they thinks is the ip for this service.
        If you assign the service IP by your own methods, do not override this
        """

    def setReady(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.

        This method exist for this kind of situations (i will explain it with a
        sample)

        Imagine a Service tree (Provider, Service, ...) for virtual machines.
        This machines will get created by the UserDeployment implementation, but,
        at some time, the machine can be put at in an state (suspend, shut down)
        that will make the transport impossible to connect with it.

        This method, in this case, will check the state of the machine, and if
        it is "ready", that is, powered on and accessible, it will return
        "State.FINISHED". If the machine is not accessible (has been erased, for
        example), it will return "State.ERROR" and store a reason of error so UDS
        can ask for it and present this information to the Administrator.

        If the machine powered off, or suspended, or any other state that is not
        directly usable but can be put in an usable state, it will return
        "State.RUNNING", and core will use checkState to see when the operation
        has finished.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        return State.FINISHED

    def deployForCache(self, cacheLevel: int):
        """
        Deploys a user deployment as cache.

        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.

        The objective of this method is providing a cache copy of an user consumable,
        and will be invoked whenever the core need to create a new copy for cache
        of the service this UserDeployment manages.

        Things to take care with this method are:

           * cacheLevel can be L1 or L2 (class constants)
           * If a deploy for cache is asked for a L1 cache, the generated
             element is expected to be all-done for user consume. L1 cache items
             will get directly assigned to users whenever needed, and are expected
             to be fast. (You always have setReady method to do anything else needed
             to assign the cache element to an user, but generally L1 cached items
             must be ready to use.
           * An L2 cache is expected to be an cached element that is "almost ready".
             The main idea behind L2 is to keep some elements almost usable by users
             but in an state that they do not consume (or consumes much less) resources.
             If your L2 cache consumes the same that L1 cache, L2 cache is in fact not
             needed.
           * This works as :py:meth:.deployForUser, meaning that you can take a look
             also to that method for more info

        :note: If your service uses caching, this method MUST be provided. If it
               do not uses cache, this method will never get called, so you can
               skip it implementation

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise Exception('Base deploy for cache invoked! for class {0}'.format(self.__class__.__name__))

    def deployForUser(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.

        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        The user parameter is not neded, but provided. It indicates the
        Database User Object (see py:mod:`uds.modules`) to which this deployed
        user service will be assigned to.

        This method will get called whenever a new deployed service for an user
        is needed. This will give this class the oportunity to create
        a service that is assigned to an user.

        The way of using this method is as follows:

        If the service gets created in "one step", that is, before the return
        of this method, the consumable service for the user gets created, it
        will return "State.FINISH".
        If the service needs more steps (as in this case), we will return
        "State.RUNNING", and if it has an error, it wil return "State.ERROR" and
        store an error string so administration interface can show it.

        We do not use user for anything, as in most cases will be.

        :note: override ALWAYS this method, or an exception will be raised

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError('Base deploy for user invoked! for class {0}'.format(self.__class__.__name__))

    def checkState(self) -> str:
        """
        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.


        If some of the initiating action tasks returns State.RUNNING. this method
        will get called until it returns State.FINISH or State.ERROR.

        In other words, whenever a multi step operation is initiated, this method
        will get the responsability to check that the operation has finished or
        failed. If the operation continues, but haven't finished yet, it must
        return State.RUNNING. If has finished must return State.FINISH and if it
        has some kind of error, State.ERROR and also store somewhere the info
        that will be requested using :py:meth:.reasonOfError

        :note: override ALWAYS this method, or an exception will be raised

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError('Base check state invoked! for class {0}'.format(self.__class__.__name__))

    def finish(self) -> None:
        """
        Invoked when the core notices that the deployment of a service has finished.
        (No matter whether it is for cache or for an user)

        This gives the opportunity to make something at that moment.

        Default implementation does nothing at all.

        :note: You can also make these operations at checkState, this is really
               not needed, but can be provided (default implementation of base class does
               nothing)
        """

    def moveToCache(self, newLevel: int) -> str:
        """
        This method is invoked whenever the core needs to move from the current
        cache level to a new cache level an user deployment.

        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.

        We only provide newLevel, because there is only two cache levels, so if
        newLevel is L1, the actual is L2, and if it is L2, the actual is L1.

        Actually there is no possibility to move assigned services again back to
        cache. If some service needs that kind of functionallity, this must be
        provided at service level (for example, when doing publishing creating
        a number of services that will be used, released and reused by users).

        Also, user deployments that are at cache level 2 will never get directly
        assigned to user. First, it will pass to L1 and then it will get assigned.

        A good sample of a real implementation of this is moving a virtual machine
        from a "suspended" state to  "running" state to assign it to an user.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        return State.FINISHED

    def userLoggedIn(self, username: str) -> None:
        """
        This method must be available so os managers can invoke it whenever
        an user get logged into a service.

        Default implementation does nothing, so if you are going to do nothing,
        you don't need to implement it.

        The responsibility of notifying it is of os manager actor, and it's
        directly invoked by os managers (right now, linux os manager and windows
        os manager)

        The user provided is just an string, that is provided by actors.
        """

    def userLoggedOut(self, username: str) -> None:
        """
        This method must be available so os managers can invoke it whenever
        an user get logged out if a service.

        Default implementation does nothing, so if you are going to do nothing,
        you don't need to implement it.

        The responability of notifying it is of os manager actor, and it's
        directly invoked by os managers (right now, linux os manager and windows
        os manager)

        The user provided is just an string, that is provided by actor.
        """

    def reasonOfError(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).

        :note: Remember that you can use ugettext to translate this error to
               user language whenever it is possible. (This one will get invoked
               directly from admin interface and, as so, will have translation
               environment correctly set up.
        """
        return 'unknown'

    def destroy(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This method gives the oportunity to remove associated data (virtual machine,
        ...) for the user consumable this instance represents.

        If return value is State.RUNNING, :py:meth:.checkState will be used to
        check if the destroy operation has finished.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError('destroy method for class {0} not provided!'.format(self.__class__.__name__))

    def cancel(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        Cancel represents a canceling of the current running operation, and
        can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).

        When administrator requests it, the cancel is "delayed" and not
        invoked directly.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        return State.RUNNING

    @classmethod
    def supportsCancel(cls) -> bool:
        """
        Helper to query if a class is custom (implements getJavascript method)
        """
        return cls.cancel != UserDeployment.cancel

    def reset(self) -> None:
        """
        This method is invoked for "reset" an user service
        This method is not intended to be a task right now, (so its one step method)
        base method does nothing
        """

    def getConnectionData(self) -> typing.Optional[typing.Tuple[str, str, str]]:
        """
        This method is only invoked on some user deployments that needs to provide
        Credentials based on deployment itself
        Returns an username, password and host
        """
        return None

    def __str__(self):
        """
        Mainly used for debugging purposses
        """
        return "Base Deployed Service"
