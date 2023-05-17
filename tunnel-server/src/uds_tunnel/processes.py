# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import multiprocessing
import asyncio
import sys
import logging
import typing

import psutil

from . import config

if typing.TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.managers import Namespace

logger = logging.getLogger(__name__)

ProcessType = typing.Callable[
    ['Connection', config.ConfigurationType, 'Namespace'],
    typing.Coroutine[typing.Any, None, None],
]

NO_CPU_PERCENT: float = 1000001.0


class Processes:
    """
    This class is used to store the processes that are used by the tunnel.
    """

    children: typing.List[
        typing.Tuple['Connection', multiprocessing.Process, psutil.Process]
    ]
    process: ProcessType
    cfg: config.ConfigurationType
    ns: 'Namespace'

    def __init__(
        self, process: ProcessType, cfg: config.ConfigurationType, ns: 'Namespace'
    ) -> None:
        self.children = []
        self.process = process  # type: ignore
        self.cfg = cfg
        self.ns = ns

        for _ in range(cfg.workers):
            self.add_child_pid()

    def add_child_pid(self):
        own_conn, child_conn = multiprocessing.Pipe()
        task = multiprocessing.Process(
            target=Processes.runner,
            args=(self.process, child_conn, self.cfg, self.ns),
        )
        task.start()
        logger.debug('ADD CHILD PID: %s', task.pid)
        self.children.append(
            (typing.cast('Connection', own_conn), task, psutil.Process(task.pid))
        )

    def best_child(self) -> 'Connection':
        best: typing.Tuple[float, 'Connection'] = (NO_CPU_PERCENT, self.children[0][0])
        missingProcesses: typing.List[int] = []
        for i, c in enumerate(self.children):
            try:
                if c[2].status() == 'zombie':  # Bad kill!!
                    raise psutil.ZombieProcess(c[2])
                percent = c[2].cpu_percent()
            except (psutil.ZombieProcess, psutil.NoSuchProcess) as e:
                # Process is missing...
                logger.warning('Missing process found: %s', e)
                try:
                    c[0].close()  # Close pipe to missing process
                except Exception:
                    logger.debug('Could not close handle for %s', e.pid)
                try:
                    c[1].kill()
                    c[1].close()
                except Exception:
                    logger.debug('Could not close process %s', e.pid)

                missingProcesses.append(i)
                continue

            logger.debug('PID %s has %s', c[2].pid, percent)

            if percent < best[0]:
                best = (percent, c[0])

        # If we have a missing process, try to add it back
        if missingProcesses:
            logger.debug('Regenerating missing processes: %s', len(missingProcesses))
            # Regenerate childs and recreate new proceeses for requests...
            # Remove missing processes
            self.children[:] = [
                child
                for i, child in enumerate(self.children)
                if i not in missingProcesses
            ]
            # Now add new children
            for (
                _
            ) in (
                missingProcesses
            ):  #  wee need to add as many as we removed, that is the len of missingProcesses
                self.add_child_pid()

            # Recheck best if all child were missing
            if best[0] == NO_CPU_PERCENT:
                return self.best_child()

        return best[1]

    def stop(self) -> None:
        # Try to stop running childs
        for i in self.children:
            try:
                i[2].kill()
            except Exception as e:
                logger.info('KILLING child %s: %s', i[2], e)

    @staticmethod
    def runner(
        proc: ProcessType,
        conn: 'Connection',
        cfg: config.ConfigurationType,
        ns: 'Namespace',
    ) -> None:
        if cfg.use_uvloop:
            try:
                import uvloop  # pylint: disable=import-outside-toplevel

                if sys.version_info >= (3, 11):
                    with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
                        runner.run(proc(conn, cfg, ns))
                else:
                    uvloop.install()
                    asyncio.run(proc(conn, cfg, ns))
            except ImportError:
                logger.warning('uvloop not found, using default asyncio')
        else:
            asyncio.run(proc(conn, cfg, ns))
