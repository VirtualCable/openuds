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

from django.utils.translation import ugettext as _
from uds.core import services
from uds.core.util.state import State

logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .service import ServiceOne, ServiceTwo


class SamplePublication(services.Publication):
    """
    This class shows how a publication is developed.

    In order to a publication to work correctly, we must provide at least the
    following methods:
        * Of course, the __init__
        * :py:meth:`.publish`
        * :py:meth:`.checkState`
        * :py:meth:`.finish`

    Also, of course, methods from :py:class:`uds.core.serializable.Serializable`


    Publication do not have an configuration interface, all data contained
    inside an instance of a Publication must be serialized if you want them between
    method calls.

    It's not waranteed that the class will not be serialized/deserialized
    between methods calls, so, first of all, implement the marshal and umnarshal
    mehods needed by all serializable classes.

    Also a thing to note is that operations requested to Publications must be
    *as fast as posible*. The operations executes in a separated thread,
    and so it cant take a bit more time to execute, but it's recommended that
    the operations executes as fast as posible, and, if it will take a long time,
    split operation so we can keep track of state.

    This means that, if we have "slow" operations, we must

    We first of all declares an estimation of how long a publication will take.
    This value is instance based, so if we override it in our class, the suggested
    time could change.

    The class attribute that indicates this suggested time is "suggestedTime", and
    it's expressed in seconds, (i.e. "suggestedTime = 10")
    """

    suggestedTime = 5  # : Suggested recheck time if publication is unfinished in seconds
    _name: str = ''
    _reason: str = ''
    _number: int = -1

    def initialize(self) -> None:
        """
        This method will be invoked by default __init__ of base class, so it gives
        us the oportunity to initialize whataver we need here.

        In our case, we setup a few attributes..
        """

        # We do not check anything at marshal method, so we ensure that
        # default values are correctly handled by marshal.
        self._name = 'test'
        self._reason = ''  # No error, no reason for it
        self._number = 1

    def marshal(self) -> bytes:
        """
        returns data from an instance of Sample Publication serialized
        """
        return '\t'.join([self._name, self._reason, str(self._number)]).encode('utf8')

    def unmarshal(self, data: bytes) -> None:
        """
        deserializes the data and loads it inside instance.
        """
        logger.debug('Data: %s', data)
        vals = data.decode('utf8').split('\t')
        logger.debug('Values: %s', vals)
        self._name = vals[0]
        self._reason = vals[1]
        self._number = int(vals[2])

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

        In our example wi will simple assign a name, and set number to 5. We
        will use this number later, to make a "delay" at check if the publication
        has finished. (see method checkState)

        We also will make this publication an "stepped one", that is, it will not
        finish at publish call but a later checkState call

        Take care with instantiating threads from here. Whenever a publish returns
        "State.RUNNING", the core will recheck it later, but not using this instance
        and maybe that even do not use this server.

        If you want to use threadings or somethin likt it, use DelayedTasks and
        do not block it. You also musht provide the mechanism to allow those
        DelayedTask to communicate with the publication.

        One sample could be, for example, to copy a bunch of files, but we know
        that this copy can take a long time and don't want it to take make it
        all here, but in a separate task. Now, do you remember that "environment"
        that is unique for every instance?, well, we can create a delayed task,
        and pass that environment (owned by this intance) as a mechanism for
        informing when the task is finished. (We insert at delayed tasks queue
        an instance, not a class itself, so we can instantiate a class and
        store it at delayed task queue.

        Also note that, in that case, this class can also acomplish that by simply
        using the suggestedTime attribute and the checkState method in most cases.
        """
        self._number = 5
        self._reason = ''
        return State.RUNNING

    def checkState(self) -> str:
        """
        Our publish method will initiate publication, but will not finish it.
        So in our sample, wi will only check if _number reaches 0, and if so
        return that we have finished, else we will return that we are working
        on it.

        One publish returns State.RUNNING, this task will get called untill
        checkState returns State.FINISHED.

        Also, wi will make the publication fail one of every 10 calls to this
        method.

        Note: Destroying an publication also makes use of this method, so you
        must keep the info of that you are checking (publishing or destroying...)
        In our case, destroy is 1-step action so this will no get called while
        destroying...
        """
        import random
        self._number -= 1
        # Serialization will take care of storing self._number

        # One of every 10 calls
        if random.randint(0, 9) == 9:
            self._reason = _('Random integer was 9!!! :-)')
            return State.ERROR

        if self._number <= 0:
            return State.FINISHED
        return State.RUNNING

    def finish(self) -> None:
        """
        Invoked when Publication manager noticed that the publication has finished.
        This give us the oportunity of cleaning up things (as stored vars, etc..),
        or initialize variables that will be needed in a later phase (by deployed
        services)

        Returned value, if any, is ignored
        """
        import string
        import random
        # Make simply a random string
        self._name = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(10))

    def reasonOfError(self) -> str:
        """
        If a publication produces an error, here we must notify the reason why
        it happened. This will be called just after publish or checkState
        if they return State.ERROR

        Returns an string, in our case, set at checkState
        """
        return self._reason

    def destroy(self) -> str:
        """
        This is called once a publication is no more needed.

        This method do whatever needed to clean up things, such as
        removing created "external" data (environment gets cleaned by core),
        etc..

        The retunred value is the same as when publishing, State.RUNNING,
        State.FINISHED or State.ERROR.
        """
        self._name = ''
        self._reason = ''  # In fact, this is not needed, but cleaning up things... :-)

        # We do not do anything else to destroy this instance of publication
        return State.FINISHED

    def cancel(self) -> str:
        """
        Invoked for canceling the current operation.
        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.

        Also, take into account that cancel is the initiation of, maybe, a
        multiple-step action, so it returns, as publish and destroy does.

        In our case, cancel simply invokes "destroy", that cleans up
        things and returns that the action has finished in 1 step.
        """
        return self.destroy()

    # Here ends the publication needed methods.
    # Methods provided below are specific for this publication
    # and will be used by user deployments that uses this kind of publication

    def getBaseName(self) -> str:
        """
        This sample method (just for this sample publication), provides
        the name generater for this publication. This is just a sample, and
        this will do the work
        """
        return self._name
