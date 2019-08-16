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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import threading
import time
import signal
import logging
import typing

from django.db import connection
from uds.core.jobs.scheduler import Scheduler
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core import jobs
from uds.core.util.Config import GlobalConfig

logger = logging.getLogger(__name__)


class SchedulerThread(threading.Thread):
    def run(self):
        Scheduler.scheduler().run()

    def notifyTermination(self):
        Scheduler.scheduler().notifyTermination()


class DelayedTaskThread(threading.Thread):
    def run(self):
        DelayedTaskRunner.runner().run()

    def notifyTermination(self):
        DelayedTaskRunner.runner().notifyTermination()


class TaskManager:
    keepRunning: bool = True

    @staticmethod
    def sigTerm(sigNum, frame):
        """
        This method will ensure that we finish correctly current running task before exiting.
        If we need to stop cause something went wrong (that should not happen), we must send sigterm, wait a while (10-20 secs) and after that send sigkill
        kill task
        sleep 10
        kill -9 task
        Take a look at killTaskManager.sh :-)
        """
        logger.info("Caught term signal, finishing task manager")
        TaskManager.keepRunning = False

    @staticmethod
    def registerJob(jobType: typing.Type[jobs.Job]):
        jobName = jobType.friendly_name
        jobs.factory().insert(jobName, jobType)

    @staticmethod
    def registerScheduledTasks():

        logger.info("Registering sheduled tasks")

        # Simply import this to make workers "auto import themself"
        from uds.core import workers  # @UnusedImport pylint: disable=unused-import

    @staticmethod
    def run():
        TaskManager.keepRunning = True

        # Don't know why, but with django 1.8, must "reset" connections so them do not fail on first access...
        # Is simmilar to https://code.djangoproject.com/ticket/21597#comment:29
        connection.close()

        # Releases owned schedules so anyone can access them...
        Scheduler.releaseOwnShedules()

        TaskManager.registerScheduledTasks()

        noSchedulers: int = GlobalConfig.SCHEDULER_THREADS.getInt()
        noDelayedTasks: int = GlobalConfig.DELAYED_TASKS_THREADS.getInt()

        logger.info('Starting %s schedulers and %s task executors', noSchedulers, noDelayedTasks)

        threads = []
        for _ in range(noSchedulers):
            thread = SchedulerThread()
            thread.start()
            threads.append(thread)
            time.sleep(0.5)  # Wait a bit before next scheduler is started

        for _ in range(noDelayedTasks):
            thread = DelayedTaskThread()
            thread.start()
            threads.append(thread)
            time.sleep(0.5)  # Wait a bit before next delayed task runner is started

        signal.signal(signal.SIGTERM, TaskManager.sigTerm)

        # Debugging stuff
        # import guppy
        # from guppy.heapy import Remote
        # Remote.on()

        # gc.set_debug(gc.DEBUG_LEAK)
        while TaskManager.keepRunning:
            time.sleep(1)

        for thread in threads:
            thread.notifyTermination()

        # The join of threads will happen before termination, so its fine to just return here
