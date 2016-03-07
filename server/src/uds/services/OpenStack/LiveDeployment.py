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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from uds.core.services import UserDeployment
from uds.core.util.State import State
from uds.core.util import log

from . import openStack

import pickle
import logging

__updated__ = '2016-03-07'


logger = logging.getLogger(__name__)

opCreate, opStart, opSuspend, opRemove, opWait, opError, opFinish, opRetry = range(8)

NO_MORE_NAMES = 'NO-NAME-ERROR'


class LiveDeployment(UserDeployment):
    '''
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.
    '''
    _name = ''
    _ip = ''
    _mac = ''
    _vmid = ''
    _reason = ''
    _queue = None

    # : Recheck every six seconds by default (for task methods)
    suggestedTime = 6

    def initialize(self):
        self._name = ''
        self._ip = ''
        self._mac = ''
        self._vmid = ''
        self._reason = ''
        self._queue = []

    # Serializable needed methods
    def marshal(self):
        '''
        Does nothing right here, we will use envoronment storage in this sample
        '''
        return '\1'.join(['v1', self._name, self._ip, self._mac, self._vmid, self._reason, pickle.dumps(self._queue)])

    def unmarshal(self, str_):
        '''
        Does nothing here also, all data are keeped at environment storage
        '''
        vals = str_.split('\1')
        if vals[0] == 'v1':
            self._name, self._ip, self._mac, self._vmid, self._reason, queue = vals[1:]
            self._queue = pickle.loads(queue)

    def getName(self):
        '''
        We override this to return a name to display. Default inplementation
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
        '''
        if self._name == '':
            try:
                self._name = self.nameGenerator().get(self.service().getBaseName(), self.service().getLenName())
            except KeyError:
                return NO_MORE_NAMES
        return self._name

    def setIp(self, ip):
        '''
        In our case, there is no OS manager associated with this, so this method
        will never get called, but we put here as sample.

        Whenever an os manager actor notifies the broker the state of the service
        (mainly machines), the implementation of that os manager can (an probably will)
        need to notify the IP of the deployed service. Remember that UDS treats with
        IP services, so will probable needed in every service that you will create.
        :note: This IP is the IP of the "consumed service", so the transport can
               access it.
        '''
        logger.debug('Setting IP to {}'.format(ip))
        self._ip = ip

    def getUniqueId(self):
        '''
        Return and unique identifier for this service.
        In our case, we will generate a mac name, that can be also as sample
        of 'mac' generator use, and probably will get used something like this
        at some services.

        The get method of a mac generator takes one param, that is the mac range
        to use to get an unused mac.
        '''
        return self._mac

    def getIp(self):
        '''
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

        '''
        return self._ip

    def setReady(self):
        '''
        The method is invoked whenever a machine is provided to an user, right
        before presenting it (via transport rendering) to the user.
        '''
        if self.cache.get('ready') == '1':
            return State.FINISHED

        status = self.service().getMachineState(self._vmid)

        if openStack.statusIsLost(status):
            return self.__error('Machine is not available anymore')

        if status == openStack.PAUSED:
            self.service().resumeMachine(self._vmid)
        elif status == openStack.STOPPED:
            self.service().startMachine(self._vmId)

        # Right now, we suppose the machine is ready

        self.cache.put('ready', '1')
        return State.FINISHED

    def getConsoleConnection(self):
        return self.service().getConsoleConnection(self._vmid)

    def desktopLogin(self, username, password, domain=''):
        return self.service().desktopLogin(self._vmId, username, password, domain)

    def notifyReadyFromOsManager(self, data):
        # Here we will check for suspending the VM (when full ready)
        logger.debug('Checking if cache 2 for {0}'.format(self._name))
        if self.__getCurrentOp() == opWait:
            logger.debug('Machine is ready. Moving to level 2')
            self.__popCurrentOp()  # Remove current state
            return self.__executeQueue()
        # Do not need to go to level 2 (opWait is in fact "waiting for moving machine to cache level 2)
        return State.FINISHED

    def deployForUser(self, user):
        '''
        Deploys an service instance for an user.
        '''
        logger.debug('Deploying for user')
        self.__initQueueForDeploy(False)
        return self.__executeQueue()

    def deployForCache(self, cacheLevel):
        '''
        Deploys an service instance for cache
        '''
        self.__initQueueForDeploy(cacheLevel == self.L2_CACHE)
        return self.__executeQueue()

    def __initQueueForDeploy(self, forLevel2=False):

        if forLevel2 is False:
            self._queue = [opCreate, opFinish]
        else:
            self._queue = [opCreate, opWait, opSuspend, opFinish]

    def __checkMachineState(self, chkState):
        logger.debug('Checking that state of machine {} ({}) is {}'.format(self._vmid, self._name, chkState))
        status = self.service().getMachineState(self._vmid)

        # If we want to check an state and machine does not exists (except in case that we whant to check this)
        if openStack.statusIsLost(status):
            return self.__error('Machine not available')

        ret = State.RUNNING

        if type(chkState) is list:
            if status in chkState:
                ret = State.FINISHED
        else:
            if status == chkState:
                ret = State.FINISHED

        return ret

    def __getCurrentOp(self):
        if len(self._queue) == 0:
            return opFinish

        return self._queue[0]

    def __popCurrentOp(self):
        if len(self._queue) == 0:
            return opFinish

        res = self._queue.pop(0)
        return res

    def __pushFrontOp(self, op):
        self._queue.insert(0, op)

    def __pushBackOp(self, op):
        self._queue.append(op)

    def __error(self, reason):
        '''
        Internal method to set object as error state

        Returns:
            State.ERROR, so we can do "return self.__error(reason)"
        '''
        logger.debug('Setting error state, reason: {0}'.format(reason))
        self.doLog(log.ERROR, reason)

        if self._vmid != '':  # Powers off & delete it
            try:
                self.service().removeMachine(self._vmid)
            except:
                logger.debug('Can\t set machine state to stopped')

        self._queue = [opError]
        self._reason = str(reason)
        return State.ERROR

    def __executeQueue(self):
        self.__debug('executeQueue')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs = {
            opCreate: self.__create,
            opRetry: self.__retry,
            opStart: self.__startMachine,
            opSuspend: self.__suspendMachine,
            opWait: self.__wait,
            opRemove: self.__remove,
        }

        try:
            execFnc = fncs.get(op, None)

            if execFnc is None:
                return self.__error('Unknown operation found at execution queue ({0})'.format(op))

            execFnc()

            return State.RUNNING
        except Exception as e:
            return self.__error(e)

    # Queue execution methods
    def __retry(self):
        '''
        Used to retry an operation
        In fact, this will not be never invoked, unless we push it twice, because
        checkState method will "pop" first item when a check operation returns State.FINISHED

        At executeQueue this return value will be ignored, and it will only be used at checkState
        '''
        return State.FINISHED

    def __wait(self):
        '''
        Executes opWait, it simply waits something "external" to end
        '''
        return State.RUNNING

    def __create(self):
        '''
        Deploys a machine from template for user/cache
        '''
        templateId = self.publication().getTemplateId()
        name = self.getName()
        if name == NO_MORE_NAMES:
            raise Exception('No more names available for this service. (Increase digits for this service to fix)')

        name = self.service().sanitizeVmName(name)  # OpenNebula don't let us to create machines with more than 15 chars!!!

        self._vmid = self.service().deployFromTemplate(name, templateId)
        if self._vmid is None:
            raise Exception('Can\'t create machine')

    def __remove(self):
        '''
        Removes a machine from system
        '''
        status = self.service().getMachineState(self._vmid)

        if openStack.statusIsLost(status):
            raise Exception('Machine not found')

        self.service().removeMachine(self._vmid)

    def __startMachine(self):
        '''
        Powers on the machine
        '''
        self.service().startMachine(self._vmid)

    def __suspendMachine(self):
        '''
        Suspends the machine
        '''
        self.service().suspendMachine(self._vmid)

    # Check methods
    def __checkCreate(self):
        '''
        Checks the state of a deploy for an user or cache
        '''
        ret = self.__checkMachineState(openStack.ACTIVE)
        if ret == State.FINISHED:
            # Get IP & MAC (early stage)
            self._mac, self._ip = self.service().getNetInfo(self._vmid)

        return ret


    def __checkStart(self):
        '''
        Checks if machine has started
        '''
        return self.__checkMachineState(openStack.ACTIVE)

    def __checkSuspend(self):
        '''
        Check if the machine has suspended
        '''
        return self.__checkMachineState(openStack.SUSPENDED)

    def __checkRemoved(self):
        '''
        Checks if a machine has been removed
        '''
        return State.FINISHED  # No check at all, always true

    def checkState(self):
        '''
        Check what operation is going on, and acts acordly to it
        '''
        self.__debug('checkState')
        op = self.__getCurrentOp()

        if op == opError:
            return State.ERROR

        if op == opFinish:
            return State.FINISHED

        fncs = {
            opCreate: self.__checkCreate,
            opRetry: self.__retry,
            opWait: self.__wait,
            opStart: self.__checkStart,
            opSuspend: self.__checkSuspend,
            opRemove: self.__checkRemoved,
        }

        try:
            chkFnc = fncs.get(op, None)

            if chkFnc is None:
                return self.__error('Unknown operation found at check queue ({0})'.format(op))

            state = chkFnc()
            if state == State.FINISHED:
                self.__popCurrentOp()  # Remove runing op
                return self.__executeQueue()

            return state
        except Exception as e:
            return self.__error(e)

    def finish(self):
        '''
        Invoked when the core notices that the deployment of a service has finished.
        (No matter wether it is for cache or for an user)
        '''
        self.__debug('finish')
        pass

    def assignToUser(self, user):
        '''
        This method is invoked whenever a cache item gets assigned to an user.
        This gives the User Deployment an oportunity to do whatever actions
        are required so the service puts at a correct state for using by a service.
        '''
        pass

    def moveToCache(self, newLevel):
        '''
        Moves machines between cache levels
        '''
        if opRemove in self._queue:
            return State.RUNNING

        if newLevel == self.L1_CACHE:
            self._queue = [opStart, opFinish]
        else:
            self._queue = [opStart, opSuspend, opFinish]

        return self.__executeQueue()

    def userLoggedIn(self, user):
        '''
        This method must be available so os managers can invoke it whenever
        an user get logged into a service.

        The user provided is just an string, that is provided by actor.
        '''
        # We store the value at storage, but never get used, just an example
        pass

    def userLoggedOut(self, user):
        '''
        This method must be available so os managers can invoke it whenever
        an user get logged out if a service.

        The user provided is just an string, that is provided by actor.
        '''
        pass

    def reasonOfError(self):
        '''
        Returns the reason of the error.

        Remember that the class is responsible of returning this whenever asked
        for it, and it will be asked everytime it's needed to be shown to the
        user (when the administation asks for it).
        '''
        return self._reason

    def destroy(self):
        '''
        Invoked for destroying a deployed service
        '''
        self.__debug('destroy')
        # If executing something, wait until finished to remove it
        # We simply replace the execution queue
        op = self.__getCurrentOp()

        if op == opError:
            return self.__error('Machine is already in error state!')

        if op == opFinish or op == opWait:
            self._queue = [opRemove, opFinish]
            return self.__executeQueue()

        self._queue = [op, opRemove, opFinish]
        # Do not execute anything.here, just continue normally
        return State.RUNNING

    def cancel(self):
        '''
        This is a task method. As that, the excepted return values are
        State values RUNNING, FINISHED or ERROR.

        This can be invoked directly by an administration or by the clean up
        of the deployed service (indirectly).
        When administrator requests it, the cancel is "delayed" and not
        invoked directly.
        '''
        return self.destroy()

    @staticmethod
    def __op2str(op):
        return {
            opCreate: 'create',
            opStart: 'start',
            opSuspend: 'suspend',
            opRemove: 'remove',
            opWait: 'wait',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
        }.get(op, '????')

    def __debug(self, txt):
        logger.debug('_name {0}: {1}'.format(txt, self._name))
        logger.debug('_ip {0}: {1}'.format(txt, self._ip))
        logger.debug('_mac {0}: {1}'.format(txt, self._mac))
        logger.debug('_vmid {0}: {1}'.format(txt, self._vmid))
        logger.debug('Queue at {0}: {1}'.format(txt, [LiveDeployment.__op2str(op) for op in self._queue]))
