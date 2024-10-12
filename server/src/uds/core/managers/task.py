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
import threading
import time
import signal
import logging
import typing

from django.db import connection
from uds.core.jobs.scheduler import Scheduler
from uds.core.jobs.delayed_task_runner import DelayedTaskRunner
from uds.core import jobs
from uds.core.util.config import GlobalConfig
from uds.core.util import singleton

logger = logging.getLogger(__name__)


class BaseThread(threading.Thread, abc.ABC):
    
    @abc.abstractmethod
    def request_stop(self) -> None:
        raise NotImplementedError


class SchedulerThread(BaseThread):
    def run(self) -> None:
        Scheduler.scheduler().run()

    def request_stop(self) -> None:
        Scheduler.scheduler().notify_termination()


class DelayedTaskThread(BaseThread):
    def run(self) -> None:
        DelayedTaskRunner.runner().run()

    def request_stop(self) -> None:
        DelayedTaskRunner.runner().request_stop()


class TaskManager(metaclass=singleton.Singleton):

    __slots__ = ('threads', 'keep_running')

    keep_running: bool
    threads: list[BaseThread]

    def __init__(self) -> None:
        self.keep_running = True
        self.threads = []

    @staticmethod
    def manager() -> 'TaskManager':
        return TaskManager()

    @staticmethod
    def sig_term(sigNum: int, frame: typing.Any) -> None:
        """
        This method will ensure that we finish correctly current running task before exiting.
        If we need to stop cause something went wrong (that should not happen), we must send sigterm, wait a while (10-20 secs) and after that send sigkill
        kill task
        sleep 10
        kill -9 task
        Take a look at killTaskManager.sh :-)
        """
        logger.info("Caught term signal, finishing task manager")
        TaskManager.manager().keep_running = False

    def register_job(self, job_type: type[jobs.Job]) -> None:
        job_name = job_type.friendly_name
        jobs.factory().register(job_name, job_type)

    def register_scheduled_tasks(self) -> None:
        logger.info("Registering sheduled tasks")

        # Simply import this to make workers "register" themselves
        from uds import workers  # pyright: ignore[reportUnusedImport]

    def add_other_tasks(self) -> None:
        logger.info("Registering other tasks")

        from uds.core.messaging.processor import MessageProcessorThread  # pylint: disable=import-outside-toplevel

        thread = MessageProcessorThread()
        thread.start()
        self.threads.append(thread)

    def run(self) -> None:
        self.keep_running = True
        # Don't know why, but with django 1.8, must "reset" connections so them do not fail on first access...
        # Is simmilar to https://code.djangoproject.com/ticket/21597#comment:29
        connection.close()

        # Releases owned schedules so anyone can access them...
        Scheduler.release_own_schedules()

        self.register_scheduled_tasks()

        n_schedulers: int = GlobalConfig.SCHEDULER_THREADS.as_int()
        n_delayed_tasks: int = GlobalConfig.DELAYED_TASKS_THREADS.as_int()

        logger.info(
            'Starting %s schedulers and %s task executors', n_schedulers, n_delayed_tasks
        )

        signal.signal(signal.SIGTERM, TaskManager.sig_term)
        signal.signal(signal.SIGINT, TaskManager.sig_term)

        thread: BaseThread
        for _ in range(n_schedulers):
            thread = SchedulerThread()
            thread.start()
            self.threads.append(thread)
            time.sleep(0.5)  # Wait a bit before next scheduler is started

        for _ in range(n_delayed_tasks):
            thread = DelayedTaskThread()
            thread.start()
            self.threads.append(thread)
            time.sleep(0.5)  # Wait a bit before next delayed task runner is started

        # Add any other tasks (Such as message processor)
        self.add_other_tasks()

        # Debugging stuff
        # import guppy
        # from guppy.heapy import Remote
        # Remote.on()

        # gc.set_debug(gc.DEBUG_LEAK)
        while self.keep_running:
            time.sleep(1)

        for thread in self.threads:
            thread.request_stop()

        # The join of threads will happen before termination, so its fine to just return here
