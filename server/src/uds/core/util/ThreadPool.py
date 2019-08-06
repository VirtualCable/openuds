# -*- coding: utf-8 -*-

#
# Copyright (c) 2013 Virtual Cable S.L.
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

from threading import Thread
import logging
import queue

logger = logging.getLogger(__name__)

DEFAULT_QUEUE_SIZE = 32


class Worker(Thread):
    def __init__(self, tasks):
        Thread.__init__(self)
        self._tasks = tasks
        self._stop = False
        self.start()

    def notifyStop(self):
        self._stop = True

    def run(self):
        while self._stop is False:
            try:
                func, args, kargs = self._tasks.get(block=True, timeout=1)
            except queue.Empty:
                continue

            try:
                func(*args, **kargs)
            except Exception:
                logger.exception('ThreadPool Worker')

            self._tasks.task_done()


class ThreadPool:
    def __init__(self, num_threads, queueSize=DEFAULT_QUEUE_SIZE):
        self._tasks = queue.Queue(queueSize)
        self._numThreads = num_threads
        self._threads = []

    def add_task(self, func, *args, **kargs):
        """
        Add a task to the queue
        """
        if not self._threads:
            for _ in range(self._numThreads):
                self._threads.append(Worker(self._tasks))

        self._tasks.put((func, args, kargs))

    def wait_completion(self):
        """
        Wait for completion of all the tasks in the queue
        """
        self._tasks.join()

        # Now we will close all running tasks
        # In case new tasks are inserted after using this, new threads will be created
        # to handle tasks
        for n in self._threads:
            n.notifyStop()

        for n in self._threads:
            n.join()

        self._threads = []
