# -*- coding: utf-8 -*-

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
import abc
import typing
import collections.abc

from uds.core.environment import Environmentable
from uds.core.serializable import Serializable

if typing.TYPE_CHECKING:
    from uds.core import services
    from uds.core import osmanagers
    from uds.core.environment import Environment
    from uds import models


class Publication(Environmentable, Serializable):
    """
    This class is in fact an interface, and defines the logic of a publication
    for a Service.

    A publication is the preparation of the needs of a service before it can
    be provided to users. One good sample of this is, in case of virtual machines,
    to copy a machine to provide COWS of this copy to users.

    As always, do not forget to invoke base class __init__ if you override it as this::

       super().__init__(environment, **kwargs)

    This is a MUST, so internal structured gets filled correctly, so don't forget it!.

    The preferred method is not to override init, but provide the :py:meth:`.initialize`,
    that will be invoked just after all internal initialization is completed.

    Normally objects of classes deriving from this one, will be serialized, called,
    deserialized. This means that all that you want to ensure that is keeped inside
    the class must be serialized and deserialized, because there is no warantee that
    the object will get two methods invoked without haven't been remoded from memory
    and loaded again, this means, IMPLEMENT marshal and unmarshal with all attributes
    that you want to keep.
    """

    # Constants for publications

    # Description of the publication

    # :Suggested time for publication finishing, in seconds
    # : This allows the manager to, if publication is no done in 1 step,
    # : re-check the publication once this time has passed, i.e. KVM COW publication
    # : takes low time, so we suggest to check at short intervals,
    # : but full clone takes a lot, so we suggest that checks are done more steady.
    # : This attribute is always accessed using an instance object, so you can
    # : change suggested_delay in your implementation.
    suggested_delay: int = 10

    _osmanager: typing.Optional['osmanagers.OSManager']
    _service: 'services.Service'
    _revision: int
    _servicepool_name: str
    _uuid: str

    _db_obj: typing.Optional['models.ServicePoolPublication']

    def __init__(self, environment: 'Environment', **kwargs):
        """
        Do not forget to invoke this in your derived class using "super(self.__class__, self).__init__(environment, values)"
        We want to use the env, cache and storage methods outside class. If not called, you must implement your own methods
        cache and storage are "convenient" methods to access _env.cache and _env.storage
        @param environment: Environment assigned to this publication
        """
        Environmentable.__init__(self, environment)
        Serializable.__init__(self)
        self._osManager = kwargs.get('osManager', None)
        self._service = kwargs['service']  # Raises an exception if service is not included
        self._revision = kwargs.get('revision', -1)
        self._servicepool_name = kwargs.get('dsName', 'Unknown')
        self._uuid = kwargs.get('uuid', '')

        self.initialize()

    def initialize(self) -> None:
        """
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base class __init__.
        This will get invoked when all initialization stuff is done, so
        you can here access service, osManager, ...
        """

    def db_obj(self) -> 'models.ServicePoolPublication':
        """
        Returns the database object associated with this publication
        """
        from uds.models import ServicePoolPublication

        if self._db_obj is None:
            self._db_obj = ServicePoolPublication.objects.get(uuid=self._uuid)
        return self._db_obj

    def service(self) -> 'services.Service':
        """
        Utility method to access parent service of this publication

        Returns

            Parent service instance object (not database object)
        """
        return self._service

    def os_manager(self) -> typing.Optional['osmanagers.OSManager']:
        """
        Utility method to access os manager for this publication.

        Returns

            Parent service instance object (not database object)
            The returned value can be None if no Os manager is needed by
            the service owner of this publication.
        """
        return self._osManager

    def revision(self) -> int:
        """
        Utility method to access the revision of this publication
        This is a numeric value, and is set by core
        """
        return self._revision

    def servicepool_name(self) -> str:
        """
        Utility method to access the declared deployed service name.

        This name is set by core, using the administrator provided data
        at administration interface.
        """
        return self._servicepool_name

    def get_uuid(self) -> str:
        return self._uuid

    @abc.abstractmethod
    def publish(self) -> str:
        """
        This method is invoked whenever the administrator requests a new publication.

        The method is not invoked directly (i mean, that the administration request
        do no makes a call to this method), but a DelayedTask is saved witch will
        initiate all publication stuff (and, of course, call this method).

        You MUST implement it, so the publication do really something.
        All publications can be synchronous or asynchronous.

        The main difference between both is that first do whatever needed, (the
        action must be fast enough to do not block core), returning State.FINISHED.

        The second (asynchronous) are publications that could block the core, so
        it have to be done in more than one step.

        An example publication could be a copy of a virtual machine, where:
            * First we invoke the copy operation to virtualization provider
            * Second, we kept needed values inside instance so we can serialize
              them whenever requested
            * Returns an State.RUNNING, indicating the core that the publication
              has started but has to finish sometime later. (We do no check
              again the state and keep waiting here, because we will block the
              core untill this operation is finished).

        :note: This method MUST be provided, an exception is raised if not.

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError(f'publish method for class {self.__class__.__name__} not provided! ')

    @abc.abstractmethod
    def check_state(self) -> str:
        """
        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.

        This method will be invoked whenever a publication is started, but it
        do not finish in 1 step. (that is, invoked as long as the instance has not 
        finished or produced an error)

        The idea behind this is simple, we can initiate an operation of publishing,
        that will be done at :py:meth:.publish method.

        If this method returns that the operation has been initiated, but not finished
        (State.RUNNING), the core will keep calling this method until check_state
        returns State.FINISHED (or State.error).

        You MUST always provide this method if you expect the publication no to be
        done in 1 step (meaning this that if publish can return State.RUNNING, this
        will get called)

        Note:
            All task methods, like this one, are expected to handle
            all exceptions, and never raise an exception from these methods
            to the core. Take that into account and handle exceptions inside
            this method.
        """
        raise NotImplementedError(f'check_state method for class {self.__class__.__name__} not provided!!!')

    def finish(self) -> None:
        """
        Invoked when Publication manager noticed that the publication has finished.
        This give us the opportunity  of cleaning up things (as stored vars, etc..)
        Returned value, if any, is ignored

        Default implementation does nothing. You can leave default method if you
        are going to do nothing.
        """
        return

    def error_reason(self) -> str:
        """
        If a publication produces an error, here we must return the reason why
        it happened. This will be called just after publish or checkPublishingState
        if they return State.ERROR

        The returned value, an string, will be used always by administration interface,
        meaning this that the translation environment will be ready, and that you
        can use gettext to return a version that can be translated to administration
        interface language.
        """
        return 'unknown'

    @abc.abstractmethod
    def destroy(self) -> str:
        """
        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.

        Invoked for destroying a deployed service
        Do whatever needed here, as deleting associated data if needed
        (i.e. a copy of the machine, snapshots, etc...)

        This method MUST be provided, even if you do nothing here (in that case,
        simply return State.FINISHED). Default implementation will raise an
        exception if it gets called

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError(f'destroy method for class {self.__class__.__name__} not provided!')

    @abc.abstractmethod
    def cancel(self) -> str:
        """
        This is a task method. As that, the expected return values are
        State values RUNNING, FINISHED or ERROR.

        This method is invoked whenever the core needs a cancelation of current
        operation. This will happen if we are, for example, preparing the
        service for users, but the administration request to stop doing this.

        This method MUST be provided, even if you do nothing here (in that case,
        simply return State.FINISHED). Default implementation will raise an
        exception if it gets called

        :note: All task methods, like this one, are expected to handle
               all exceptions, and never raise an exception from these methods
               to the core. Take that into account and handle exceptions inside
               this method.
        """
        raise NotImplementedError(f'cancel method for class {self.__class__.__name__} not provided!')

    def __str__(self):
        """
        String method, mainly used for debugging purposes
        """
        return 'Base Publication'
