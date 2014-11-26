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

from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
from django.conf import settings

from django.utils.daemonize import become_daemon
from uds.core.managers.TaskManager import TaskManager
from uds.core.util.Config import GlobalConfig
import logging
import sys
import os
import signal
import time
import six

logger = logging.getLogger(__name__)

PID_FILE = 'taskmanager.pid'


def getPidFile():
    return settings.BASE_DIR + '/' + PID_FILE


class Command(BaseCommand):
    args = "None"
    help = "Executes the task manager as a daemon. No parameter show current status of task manager"

    option_list = BaseCommand.option_list + (
        make_option('--start',
                    action='store_true',
                    dest='start',
                    default=False,
                    help='Starts a new daemon'),
        make_option('--stop',
                    action='store_true',
                    dest='stop',
                    default=False,
                    help='Stop any running daemon'),
    )

    def handle(self, *args, **options):
        logger.info("Running task manager command")

        GlobalConfig.initialize()

        start = options['start'] and True or False
        stop = options['stop'] and True or False

        pid = None
        try:
            pid = int(file(getPidFile(), 'r').readline())
        except Exception:
            pid = None

        if stop is True and pid is not None:
            try:
                logger.info('Stopping task manager. pid: {0}'.format(pid))
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)  # Wait a bit before running new one
                os.unlink(getPidFile())
            except Exception:
                logger.error("Could not stop task manager (maybe it's not runing?)")
                os.unlink(getPidFile())

        if start is True:
            logger.info('Starting task manager.')
            become_daemon(settings.BASE_DIR, settings.LOGDIR + '/taskManagerStdout.log', settings.LOGDIR + '/taskManagerStderr.log')
            pid = six.text_type(os.getpid())

            open(getPidFile(), 'w+').write("%s\n" % pid)

            manager = TaskManager()
            manager.run()

        if start is False and stop is False:
            if pid is not None:
                sys.stdout.write("Task manager found running (pid file exists: {0})\n".format(pid))
            else:
                sys.stdout.write("Task manager not foud (pid file do not exits)\n")
