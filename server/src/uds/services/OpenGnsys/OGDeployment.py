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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from uds.core.services import UserDeployment
from uds.core.util.State import State
from uds.core.util import log
from uds.models.Util import getSqlDatetime

from . import og
import six

import pickle
import logging

__updated__ = '2017-05-19'


logger = logging.getLogger(__name__)

opCreate, opError, opFinish, opRemove, opRetry = range(5)


class OGDeployment(UserDeployment):
    '''
    This class generates the user consumable elements of the service tree.

    After creating at administration interface an Deployed Service, UDS will
    create consumable services for users using UserDeployment class as
    provider of this elements.

    The logic for managing ovirt deployments (user machines in this case) is here.

    '''

    # : Recheck every six seconds by default (for task methods)
    suggestedTime = 20

    def initialize(self):
        self._name = ''
        self._ip = ''
        self._mac = ''
        self._machineId = ''
        self._stamp = 0
        self._reason = ''
        self._queue = []

    # Serializable needed methods
    def marshal(self):
        '''
        Does nothing right here, we will use envoronment storage in this sample
        '''
        return '\1'.join(['v1', self._name, self._ip, self._mac, self._machineId, self._reason, six.text_type(self._stamp), pickle.dumps(self._queue)])

    def unmarshal(self, str_):
        '''
        Does nothing here also, all data are keeped at environment storage
        '''
        vals = str_.split('\1')
        if vals[0] == 'v1':
            self._name, self._ip, self._mac, self._machineId, self._reason, stamp, queue = vals[1:]
            self._stamp = int(stamp)
            self._queue = pickle.loads(queue)

    def getName(self):
        return self._name

    def getUniqueId(self):
        return self._mac.upper()

    def getIp(self):
        return self._ip

    def setReady(self):
        '''
        Right now, this does nothing on OG.
        The machine has been already been started.
        The problem is that currently there is no way that a machine is in FACT started.
        OpenGnsys will try it best by sending an WOL
        '''
        # if self.cache.get('ready') == '1':
        #    return State.FINISHED

        # status = self.service().status(self._machineId)
        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        # if status['status'] != 'off':
        #     self.cache.put('ready', '1')
        #     return State.FINISHED

        # Return back machine to preparing?...
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
        self.__initQueueForDeploy()  # No Level2 Cache possible
        return self.__executeQueue()

    def __initQueueForDeploy(self):

        self._queue = [opCreate, opFinish]

    def __checkMachineReady(self):
        logger.debug('Checking that state of machine {} ({}) is ready'.format(self._machineId, self._name))

        try:
            status = self.service().status(self._machineId)
        except Exception as e:
            logger.exception('Exception at checkMachineReady')
            return self.__error('Error checking machine: {}'.format(e))

        # possible status are ("off", "oglive", "busy", "linux", "windows", "macos" o "unknown").
        if status['status'] in ("linux", "windows", "macos"):
            return State.FINISHED

        return State.RUNNING

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

        # TODO: Unreserve machine?? Maybe it just better to keep it assigned so UDS don't get it again in a while...

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
            opRemove: self.__remove,
        }

        try:
            execFnc = fncs.get(op, None)

            if execFnc is None:
                return self.__error('Unknown operation found at execution queue ({0})'.format(op))

            execFnc()

            return State.RUNNING
        except Exception as e:
            logger.exception('Got Exception')
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

    def __create(self):
        '''
        Deploys a machine from template for user/cache
        '''
        try:
            r = self.service().reserve()
        except Exception as e:
            logger.exception('Creating machine')
            return self.__error('Error creating reservation: {}'.format(e))

        self._machineId = r['id']
        self._name = r['name']
        self._mac = r['mac']
        self._ip = r['ip']
        self._stamp = getSqlDatetime(unix=True)
        # Store actor version
        self.dbservice().setProperty('actor_version', '1.0-OpenGnsys')

    def __remove(self):
        '''
        Removes a machine from system
        '''
        self.service().unreserve(self._machineId)

    # Check methods
    def __checkCreate(self):
        '''
        Checks the state of a deploy for an user or cache
        '''
        return self.__checkMachineReady()

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
        self._queue = [opRemove, opFinish]
        return self.__executeQueue()

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
            opRemove: 'remove',
            opError: 'error',
            opFinish: 'finish',
            opRetry: 'retry',
        }.get(op, '????')

    def __debug(self, txt):
        logger.debug('_name {0}: {1}'.format(txt, self._name))
        logger.debug('_ip {0}: {1}'.format(txt, self._ip))
        logger.debug('_mac {0}: {1}'.format(txt, self._mac))
        logger.debug('_machineId {0}: {1}'.format(txt, self._machineId))
        logger.debug('Queue at {0}: {1}'.format(txt, [OGDeployment.__op2str(op) for op in self._queue]))
