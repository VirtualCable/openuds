# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import sys
import os
import time
import atexit
from signal import SIGTERM, SIGKILL

from udsactor.log import logger


class Daemon:
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """

    def __init__(self, pidfile: str, stdin: str = '/dev/null', stdout: str = '/dev/null', stderr: str = '/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self) -> None:
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError as e:
            logger.error("fork #1 error: {}".format(e))
            sys.stderr.write("fork #1 failed: {}\n".format(e))
            sys.exit(1)

        # decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent
                sys.exit(0)
        except OSError as e:
            logger.error("fork #2 error: {}".format(e))
            sys.stderr.write("fork #2 failed: {}\n".format(e))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(self.stdin, 'r')
        so = open(self.stdout, 'ab+')
        se = open(self.stderr, 'ab+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.removePidFile)
        pidStr = str(os.getpid())
        with open(self.pidfile, 'w+') as f:
            f.write("{}\n".format(pidStr))

    def removePidFile(self) -> None:
        try:
            os.remove(self.pidfile)
        except Exception:  # nosec: Not interested in exception
            # Not found/not permissions or whatever, ignore it
            pass

    def start(self) -> None:
        """
        Start the daemon
        """
        logger.debug('Starting daemon')
        # Check for a pidfile to see if the daemon already runs
        if os.path.exists(self.pidfile):
            message = "pidfile {} already exist. Daemon already running?\n".format(self.pidfile)
            logger.error(message)
            sys.stderr.write(message)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        try:
            self.run()
        except Exception as e:
            logger.error('Exception running process: {}'.format(e))

        self.removePidFile()

    def stop(self) -> None:
        """
        Stop the daemon
        """
        # Get the pid from the pidfile
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            message = "pidfile {} does not exist. Daemon not running?\n".format(self.pidfile)
            logger.error(message)
            # sys.stderr.write(message)
            return  # not an error in a restart

        # Try killing the daemon process
        try:
            cnt = 10
            while cnt:
                cnt -= 1
                os.kill(pid, SIGTERM)
                time.sleep(1)

            if not cnt:
                os.kill(pid, SIGKILL)
        except OSError as err:
            if err.errno == 3:  # No such process
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                sys.stderr.write('Error: {}'.format(err))
                sys.exit(1)

    def restart(self) -> None:
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    # Overridables
    def run(self) -> None:
        """
        override this to provide your own daemon
        """
