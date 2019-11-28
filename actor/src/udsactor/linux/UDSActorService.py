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
import signal
import typing

from . import operations
from . import renamer
from . import daemon

from ..log import logger
from ..service import CommonService


try:
    from prctl import set_proctitle  # @UnresolvedImport
except ImportError:  # Platform may not include prctl, so in case it's not available, we let the "name" as is
    def set_proctitle(_):
        pass


class UDSActorSvc(daemon.Daemon, CommonService):
    def __init__(self, args=None) -> None:
        daemon.Daemon.__init__(self, '/var/run/udsactor.pid')
        CommonService.__init__(self)

        signal.signal(signal.SIGINT, self.markForExit)
        signal.signal(signal.SIGTERM, self.markForExit)


    def markForExit(self, signum, frame):
        self._isAlive = False


    def rename(  # pylint: disable=unused-argument
            self,
            name: str,
            userName: typing.Optional[str] = None,
            oldPassword: typing.Optional[str] = None,
            newPassword: typing.Optional[str] = None
        ) -> None:
        '''
        Renames the computer, and optionally sets a password for an user
        before this
        '''
        hostName = operations.getComputerName()

        if hostName.lower() == name.lower():
            logger.info('Computer name is already {}'.format(hostName))
            return

        # Check for password change request for an user
        if userName and oldPassword and newPassword:
            logger.info('Setting password for user {}'.format(userName))
            try:
                operations.changeUserPassword(userName, oldPassword, newPassword)
            except Exception as e:
                # We stop here without even renaming computer, because the
                # process has failed
                raise Exception('Could not change password for user {} (maybe invalid current password is configured at broker): {} '.format(userName, e))

        renamer.rename(name)

    def joinDomain(  # pylint: disable=unused-argument, too-many-arguments
            self,
            name: str,
            domain: str,
            ou: str,
            account: str,
            password: str
        ) -> None:
        logger.fatal('Join domain is not supported on linux platforms right now')

    def run(self):
        logger.debug('Running Daemon')
        set_proctitle('UDSActorDaemon')

        # Linux daemon will continue running unless something is requested to
        if not self.initialize():
            return # Stop daemon if initializes told to do so

        # Initialization is done, set machine to ready for UDS, communicate urls, etc...
        self.setReady()

        # *********************
        # * Main Service loop *
        # *********************
        # Counter used to check ip changes only once every 10 seconds, for
        # example
        counter = 0
        while self.isAlive:
            counter += 1
            if counter % 10 == 0:
                self.checkIpsChanged()
            # In milliseconds, will break
            self.doWait(1000)

        self.notifyStop()


def usage():
    sys.stderr.write("usage: {} start|stop|restart|login 'username'|logout 'username'\n".format(sys.argv[0]))
    sys.exit(2)


if __name__ == '__main__':
    logger.setLevel(20000)

    if len(sys.argv) == 3 and sys.argv[1] in ('login', 'logout'):
        logger.debug('Running client udsactor')
        # client = None
        # try:
        #     client = ipc.ClientIPC(IPC_PORT)
        #     if 'login' == sys.argv[1]:
        #         client.sendLogin(sys.argv[2])
        #         sys.exit(0)
        #     elif 'logout' == sys.argv[1]:
        #         client.sendLogout(sys.argv[2])
        #         sys.exit(0)
        #     else:
        #         usage()
        # except Exception as e:
        #     logger.error(e)
    elif len(sys.argv) != 2:
        usage()

    logger.debug('Executing actor')
    daemonSvr = UDSActorSvc()
    if len(sys.argv) == 2:
        if sys.argv[1] == 'start':
            daemonSvr.start()
        elif sys.argv[1] == 'stop':
            daemonSvr.stop()
        elif sys.argv[1] == 'restart':
            daemonSvr.restart()
        else:
            usage()
        sys.exit(0)
    else:
        usage()
