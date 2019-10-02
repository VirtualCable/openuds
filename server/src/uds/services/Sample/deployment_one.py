# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

from uds.core import services
from uds.core.util.state import State

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds import models
    from .service import ServiceOne
    from .publication import SamplePublication

logger = logging.getLogger(__name__)


class SampleUserDeploymentOne(services.UserDeployment):
    """
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.


    At class instantiation, this will receive an environment with"generator",
    that are classes that provides a way to generate unique items.

    The generators provided right now are 'mac' and 'name'. To get more info
    about this, look at py:class:`uds.core.util.unique_mac_generator.UniqueNameGenerator`
    and py:class:`uds.core.util.unique_name_generator.UniqueNameGenerator`

    This first sample do not uses cache. To see one with cache, see
    SampleUserDeploymentTwo. The main difference are the "...Cache".." methods,
    that here are not needed.

    As sample also of environment storage usage, wi will use here the provider
    storage to keep all our needed info, leaving marshal and unmarshal (needed
    by Serializble classes, like this) empty (that is, returns '' first and does
    nothing the second one)

    Also Remember, if you don't include this class as the deployedType of the
    SampleServiceOne, or whenever you trie to access a service of SampleServiceOne,
    you will get an excetion that says that you havent included the deployedType.
    """

    # : Recheck every five seconds by default (for task methods)
    suggestedTime = 5

    # Serializable needed methods
    def marshal(self) -> bytes:
        """
        Does nothing right here, we will use environment storage in this sample
        """
        return b''

    def unmarshal(self, data: bytes) -> None:
        """
        Does nothing here also, all data are kept at environment storage
        """

    def getName(self) -> str:
        """
        We override this to return a name to display. Default implementation
        (in base class), returns getUniqueIde() value
        This name will help user to identify elements, and is only used
        at administration interface.

        We will use here the environment name provided generator to generate
        a name for this element.

        The namaGenerator need two params, the base name and a length for a
        numeric incremental part for generating unique names. This are unique for
        all UDS names generations, that is, UDS will not generate this name again
        until this name is freed, or object is removed, what makes its environment
        to also get removed, that makes all uniques ids (names and macs right now)
        to also get released.

        Every time get method of a generator gets called, the generator creates
        a new unique name, so we keep the first generated name cached and don't
        generate more names. (Generator are simple utility classes)
        """
        name: str = typing.cast(str, self.storage.readData('name'))
        if name is None:
            name = self.nameGenerator().get(self.service().getBaseName() + '-' + self.service().getColour(), 3)
            # Store value for persistence
            self.storage.saveData('name', name)

        return name

    def setIp(self, ip: str) -> None:
        """
        In our case, there is no OS manager associated with this, so this method
        will never get called, but we put here as sample.

        Whenever an os manager actor notifies the broker the state of the service
        (mainly machines), the implementation of that os manager can (an probably will)
        need to notify the IP of the deployed service. Remember that UDS treats with
        IP services, so will probable needed in every service that you will create.
        :note: This IP is the IP of the "consumed service", so the transport can
               access it.
        """
        self.storage.saveData('ip', ip)

    def getUniqueId(self) -> str:
        """
        Return and unique identifier for this service.
        In our case, we will generate a mac name, that can be also as sample
        of 'mac' generator use, and probably will get used something like this
        at some services.

        The get method of a mac generator takes one param, that is the mac range
        to use to get an unused mac.
        """
        mac = typing.cast(str, self.storage.readData('mac'))
        if mac is None:
            mac = self.macGenerator().get('00:00:00:00:00:00-00:FF:FF:FF:FF:FF')
            self.storage.saveData('mac', mac)
        return mac

    def getIp(self) -> str:
        """
        We need to implement this method, so we can return the IP for transports
        use. If no IP is known for this service, this must return None

        If our sample do not returns an IP, IP transport will never work with
        this service. Remember in real cases to return a valid IP address if
        the service is accesible and you alredy know that (for example, because
        the IP has been assigend via setIp by an os manager) or because
        you get it for some other method.

        Storage returns None if key is not stored.

        :note: Keeping the IP address is responsibility of the User Deployment.
               Every time the core needs to provide the service to the user, or
               show the IP to the administrator, this method will get called

        """
        ip = typing.cast(str, self.storage.readData('ip'))
        if ip is None:
            ip = '192.168.0.34'  # Sample IP for testing purposses only
        return ip

    def setReady(self) -> str:
        """
        This is a task method. As that, the expected return values are
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
        it is "ready", that is, powered on and accesible, it will return
        "State.FINISHED". If the machine is not accesible (has ben erased, for
        example), it will return "State.ERROR" and store a reason of error so UDS
        can ask for it and present this information to the Administrator.

        If the machine powered off, or suspended, or any other state that is not
        directly usable but can be put in an usable state, it will return
        "State.RUNNING", and core will use checkState to see when the operation
        has finished.

        I hope this sample is enough to explain the use of this method..
        """

        # In our case, the service is always ready
        return State.FINISHED

    def deployForUser(self, user: 'models.User') -> str:
        """
        Deploys an service instance for an user.

        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        The user parameter is not realy neded, but provided. It indicates the
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
        """
        import random

        self.storage.saveData('count', '0')

        # random fail
        if random.randint(0, 9) == 9:
            self.storage.saveData('error', 'Random error at deployForUser :-)')
            return State.ERROR

        return State.RUNNING

    def checkState(self) -> str:
        """
        Our deployForUser method will initiate the consumable service deployment,
        but will not finish it.

        So in our sample, we will only check if a number reaches 5, and if so
        return that we have finished, else we will return that we are working
        on it.

        One deployForUser returns State.RUNNING, this task will get called until
        checkState returns State.FINISHED.

        Also, we will make the publication fail one of every 10 calls to this
        method.

        Note: Destroying, canceling and deploying for cache also makes use of
        this method, so you must keep the info of that you are checking if you
        need it.
        In our case, destroy is 1-step action so this will no get called while
        destroying, and cancel will simply invoke destroy
        """
        import random
        countStr: typing.Optional[str] = typing.cast(str, self.storage.readData('count'))
        count: int = 0
        if countStr:
            count = int(countStr) + 1
        # Count is always a valid value, because this method will never get
        # called before deployForUser, deployForCache, destroy or cancel.
        # In our sample, we only use checkState in case of deployForUser,
        # so at first call count will be 0.
        if count >= 5:
            return State.FINISHED

        # random fail
        if random.randint(0, 9) == 9:
            self.storage.saveData('error', 'Random error at checkState :-)')
            return State.ERROR

        self.storage.saveData('count', str(count))
        return State.RUNNING

    def finish(self) -> None:
        """
        Invoked when the core notices that the deployment of a service has finished.
        (No matter wether it is for cache or for an user)

        This gives the oportunity to make something at that moment.
        :note: You can also make these operations at checkState, this is really
        not needed, but can be provided (default implementation of base class does
        nothing)
        """
        # Note that this is not really needed, is just a sample of storage use
        self.storage.remove('count')

    def userLoggedIn(self, username: str) -> None:
        """
        This method must be available so os managers can invoke it whenever
        an user get logged into a service.

        Default implementation does nothing, so if you are going to do nothing,
        you don't need to implement it.

        The responability of notifying it is of os manager actor, and it's
        directly invoked by os managers (right now, linux os manager and windows
        os manager)

        The user provided is just an string, that is provided by actor.
        """
        # We store the value at storage, but never get used, just an example
        self.storage.saveData('user', username)

    def userLoggedOut(self, username) -> None:
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
        # We do nothing more that remove the user
        self.storage.remove('user')

    def reasonOfError(self) -> str:
        """
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        """
        return typing.cast(str, self.storage.readData('error')) or 'No error'

    def destroy(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        Invoked for destroying a deployed service
        Do whatever needed here, as deleting associated data if needed (i.e. a copy of the machine, snapshots, etc...)
        @return: State.FINISHED if no more checks/steps for deployment are needed, State.RUNNING if more steps are needed (steps checked using checkState)
        """
        return State.FINISHED

    def cancel(self) -> str:
        """
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        """
        return State.FINISHED
