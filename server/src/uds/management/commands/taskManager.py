# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
import argparse
import sys
import os
import signal
import time
import logging
import typing

from django.core.management.base import BaseCommand  # , CommandError
from django.conf import settings

from uds.core.managers import task_manager
from uds.core.util.config import GlobalConfig

logger = logging.getLogger(__name__)

PID_FILE = 'taskmanager.pid'


def pid_file_path() -> str:
    return settings.BASE_DIR + '/' + PID_FILE


# become_daemon seems te be removed on django 1.9
# This is a copy of posix version from django 1.8
def become_daemon(
    our_home_dir: str = '.',
    out_log: str = '/dev/null',
    err_log: str = '/dev/null',
    umask: int = 0o022,
) -> None:
    """Robustly turn into a UNIX daemon, running in our_home_dir."""
    # First fork
    try:
        if os.fork() > 0:
            sys.exit(0)  # kill off parent
    except OSError as e:
        sys.stderr.write(f'fork #1 failed: ({e.errno}) {e.strerror}')
        sys.exit(1)
    os.setsid()
    os.chdir(our_home_dir)
    os.umask(umask)

    # Second fork
    try:
        if os.fork() > 0:
            os._exit(0)  # pylint: disable=protected-access
    except OSError as e:
        sys.stderr.write(f'fork #2 failed: ({e.errno}) {e.strerror}')
        os._exit(1)  # pylint: disable=protected-access

    si = open('/dev/null', 'r', encoding='utf-8')  # pylint: disable=consider-using-with
    so = open(out_log, 'a+', 1, encoding='utf-8')  # pylint: disable=consider-using-with
    se = open(err_log, 'a+', 1, encoding='utf-8')  # pylint: disable=consider-using-with
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    # Set custom file descriptors so that they get proper buffering.
    sys.stdout, sys.stderr = so, se


class Command(BaseCommand):
    args = "None"
    help = "Executes the task manager as a daemon. No parameter show current status of task manager"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            '--start',
            action='store_true',
            dest='start',
            default=False,
            help='Starts a new daemon',
        )
        parser.add_argument(
            '--stop',
            action='store_true',
            dest='stop',
            default=False,
            help='Stop any running daemon',
        )
        parser.add_argument(
            '--foreground',
            action='store_true',
            dest='foreground',
            default=True,
            help='Stop any running daemon',
        )
        parser.add_argument(
            '--background',
            action='store_false',
            dest='foreground',
            default=True,
            help='Stop any running daemon',
        )

    def handle(self, *args: typing.Any, **options: typing.Any) -> None:
        logger.info("Running task manager command")

        GlobalConfig.initialize()

        start = options.get('start', False)
        stop = options.get('stop', False)
        foreground = options.get('foreground', False)

        logger.debug('Start: %s, Stop: %s, Foreground: %s', start, stop, foreground)

        pid: int = 0
        try:
            pid = int(open(pid_file_path(), 'r', encoding='utf8').readline())
        except Exception:
            pid = 0

        if stop and pid:
            try:
                logger.info('Stopping task manager. pid: %s', pid)
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)  # Wait a bit before running new one
                os.unlink(pid_file_path())
            except Exception:
                logger.error("Could not stop task manager (maybe it's not runing?)")
                os.unlink(pid_file_path())

        if start:
            logger.info('Starting task manager.')

            if not foreground:
                become_daemon(
                    settings.BASE_DIR,
                    settings.LOGDIR + '/taskManagerStdout.log',
                    settings.LOGDIR + '/taskManagerStderr.log',
                )
                pid = os.getpid()

                with open(pid_file_path(), 'w+', encoding='utf8') as f:
                    f.write(f'{pid}\n')

            manager = task_manager()
            manager.run()

        if not start and not stop:
            if pid:
                self.stdout.write(
                    f'Task manager found running (pid file exists: {pid})\n'
                )
            else:
                self.stdout.write("Task manager not found (pid file do not exits)\n")
