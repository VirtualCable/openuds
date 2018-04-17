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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.db import transaction, connection
from django.db.models import Q
from uds.models import DelayedTask as dbDelayedTask
from uds.models import getSqlDatetime
from uds.core.Environment import Environment
from uds.core.util import encoders
from socket import gethostname
from pickle import loads, dumps
from datetime import timedelta
import threading
import time
import logging

__updated__ = '2018-03-02'

logger = logging.getLogger(__name__)


class DelayedTaskThread(threading.Thread):
    '''
    Class responsible of executing a delayed task in its own thread
    '''
    def __init__(self, taskInstance):
        super(DelayedTaskThread, self).__init__()
        self._taskInstance = taskInstance

    def run(self):
        try:
            self._taskInstance.execute()
        except Exception as e:
            logger.exception("Exception in thread {0}: {1}".format(e.__class__, e))


class DelayedTaskRunner(object):
    '''
    Delayed task runner class
    '''
    # How often tasks r checked
    granularity = 2

    # to keep singleton DelayedTaskRunner
    _runner = None

    def __init__(self):
        logger.debug("Initializing delayed task runner")
        self._hostname = gethostname()
        self._keepRunning = True

    def notifyTermination(self):
        '''
        Invoke this whenever you want to terminate the delayed task runner thread
        It will mark the thread to "stop" ASAP
        '''
        self._keepRunning = False

    @staticmethod
    def runner():
        '''
        Static method that returns an instance (singleton instance) to a Delayed Runner.
        There is only one instance of DelayedTaksRunner, but its "run" method is executed on
        many thread (depending on configuration). They all share common Instance data
        '''
        if DelayedTaskRunner._runner is None:
            DelayedTaskRunner._runner = DelayedTaskRunner()
        return DelayedTaskRunner._runner

    def executeOneDelayedTask(self):
        now = getSqlDatetime()
        filt = Q(execution_time__lt=now) | Q(insert_date__gt=now + timedelta(seconds=30))
        # If next execution is before now or last execution is in the future (clock changed on this server, we take that task as executable)
        taskInstance = None
        try:
            with transaction.atomic():  # Encloses
                task = dbDelayedTask.objects.select_for_update().filter(filt).order_by('execution_time')[0]  # @UndefinedVariable
                if task.insert_date > now + timedelta(seconds=30):
                    logger.warning('EXecuted {} due to insert_date being in the future!'.format(task.type))
                taskInstanceDump = encoders.decode(task.instance, 'base64')
                task.delete()
            taskInstance = loads(taskInstanceDump)
        except Exception:
            # Transaction have been rolled back using the "with atomic", so here just return
            # Note that is taskInstance can't be loaded, this task will not be retried
            return

        if taskInstance is not None:
            logger.debug('Executing delayedTask:>{0}<'.format(task))
            taskInstance.env = Environment.getEnvForType(taskInstance.__class__)
            DelayedTaskThread(taskInstance).start()

    def __insert(self, instance, delay, tag):
        now = getSqlDatetime()
        exec_time = now + timedelta(seconds=delay)
        cls = instance.__class__
        instanceDump = encoders.encode(dumps(instance), 'base64')
        typeName = str(cls.__module__ + '.' + cls.__name__)

        logger.debug('Inserting delayed task {0} with {1} bytes ({2})'.format(typeName, len(instanceDump), exec_time))

        dbDelayedTask.objects.create(type=typeName, instance=instanceDump,  # @UndefinedVariable
                                     insert_date=now, execution_delay=delay, execution_time=exec_time, tag=tag)

    def insert(self, instance, delay, tag=''):
        retries = 3
        while retries > 0:
            retries -= 1
            try:
                self.__insert(instance, delay, tag)
                break
            except Exception as e:
                logger.info('Exception inserting a delayed task {0}: {1}'.format(str(e.__class__), e))
                try:
                    connection.close()
                except Exception:
                    logger.exception('Closing db connection at insert')
                time.sleep(1)  # Wait a bit before next try...
        # If retries == 0, this is a big error
        if retries == 0:
            logger.error("Could not insert delayed task!!!! {0} {1} {2}".format(instance, delay, tag))
            return False
        return True

    def remove(self, tag):
        try:
            with transaction.atomic():
                dbDelayedTask.objects.select_for_update().filter(tag=tag).delete()  # @UndefinedVariable
        except Exception as e:
            logger.exception('Exception removing a delayed task {0}: {1}'.format(str(e.__class__), e))

    def checkExists(self, tag):

        if tag == '' or tag is None:
            return False

        number = 0
        try:
            number = dbDelayedTask.objects.filter(tag=tag).count()  # @UndefinedVariable
        except Exception:
            logger.error('Exception looking for a delayed task tag {0}'.format(tag))
        return number > 0

    def run(self):
        logger.debug("At loop")
        while self._keepRunning:
            try:
                time.sleep(self.granularity)
                self.executeOneDelayedTask()
            except Exception as e:
                logger.error('Unexpected exception at run loop {0}: {1}'.format(e.__class__, e))
                try:
                    connection.close()
                except Exception:
                    logger.exception('Exception clossing connection at delayed task')
        logger.info('Exiting DelayedTask Runner because stop has been requested')
