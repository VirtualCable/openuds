# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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

from udsactor import operations

from udsactor.service import CommonService
from udsactor.service import initCfg
from udsactor.service import IPC_PORT

from udsactor import ipc

from udsactor.log import logger

from udsactor.linux.daemon import Daemon
from udsactor.linux import renamer

import sys
import os
import stat
import subprocess

POST_CMD = '/etc/udsactor/post'
PRECONNECT_CMD = '/etc/udsactor/pre'

try:
    from prctl import set_proctitle  # @UnresolvedImport
except Exception:  # Platform may not include prctl, so in case it's not available, we let the "name" as is
    def set_proctitle(_):
        pass


class UDSActorSvc(Daemon, CommonService):
    rebootMachineAfterOp = False

    def __init__(self, args=None):
        Daemon.__init__(self, '/var/run/udsa.pid')
        CommonService.__init__(self)

    def rename(self, name, user=None, oldPassword=None, newPassword=None):
        '''
        Renames the computer, and optionally sets a password for an user
        before this
        '''
        hostName = operations.getComputerName()

        if hostName.lower() == name.lower():
            logger.info('Computer name is already {}'.format(hostName))
            self.setReady()
            return

        # Check for password change request for an user
        if user is not None:
            logger.info('Setting password for user {}'.format(user))
            try:
                operations.changeUserPassword(user, oldPassword, newPassword)
            except Exception as e:
                # We stop here without even renaming computer, because the
                # process has failed
                raise Exception(
                    'Could not change password for user {} (maybe invalid current password is configured at broker): {} '.format(user, unicode(e)))

        renamer.rename(name)

        if self.rebootMachineAfterOp is False:
            self.setReady()
        else:
            logger.info('Rebooting computer to activate new name {}'.format(name))
            self.reboot()


    def joinDomain(self, name, domain, ou, account, password):
        logger.fatal('Join domain is not supported on linux platforms right now')

    def preConnect(self, user, protocol):
        '''
        Invoked when received a PRE Connection request via REST
        '''
        # Execute script in /etc/udsactor/post after interacting with broker, if no reboot is requested ofc
        # This will be executed only when machine gets "ready"
        try:

            if os.path.isfile(PRECONNECT_CMD):
                if (os.stat(PRECONNECT_CMD).st_mode & stat.S_IXUSR) != 0:
                    subprocess.call([PRECONNECT_CMD, user, protocol])
                else:
                    logger.info('PRECONNECT file exists but it it is not executable (needs execution permission by root)')
            else:
                logger.info('PRECONNECT file not found & not executed')
        except Exception as e:
            # Ignore output of execution command
            logger.error('Executing preconnect command give')


    def run(self):
        cfg = initCfg()  # Gets a local copy of config to get "reboot"

        logger.debug('CFG: {}'.format(cfg))

        if cfg is not None:
            self.rebootMachineAfterOp = cfg.get('reboot', True)
        else:
            self.rebootMachineAfterOp = False

        logger.info('Reboot after is {}'.format(self.rebootMachineAfterOp))

        logger.debug('Running Daemon')
        set_proctitle('UDSActorDaemon')

        # Linux daemon will continue running unless something is requested to
        while True:
            brokerConnected = self.interactWithBroker()
            if brokerConnected is False:
                logger.debug('Interact with broker returned false, stopping service after a while')
                return
            elif brokerConnected is True:
                break

            # If brokerConnected returns None, repeat the cycle
            self.doWait(16000)  # Wait for a looong while

        if self.isAlive is False:
            logger.debug('The service is not alive after broker interaction, stopping it')
            return

        if self.rebootRequested is True:
            logger.debug('Reboot has been requested, stopping service')
            return

        # Execute script in /etc/udsactor/post after interacting with broker, if no reboot is requested ofc
        # This will be executed only when machine gets "ready"
        try:

            if os.path.isfile(POST_CMD):
                if (os.stat(POST_CMD).st_mode & stat.S_IXUSR) != 0:
                    subprocess.call([POST_CMD, ])
                else:
                    logger.info('POST file exists but it it is not executable (needs execution permission by root)')
            else:
                logger.info('POST file not found & not executed')
        except Exception as e:
            # Ignore output of execution command
            logger.error('Executing post command give')

        self.initIPC()

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

        self.endIPC()
        self.endAPI()

        self.notifyStop()


def usage():
    sys.stderr.write("usage: {} start|stop|restart|login 'username'|logout 'username'\n".format(sys.argv[0]))
    sys.exit(2)

if __name__ == '__main__':
    logger.setLevel(20000)

    if len(sys.argv) == 3 and sys.argv[1] in ('login', 'logout'):
        logger.debug('Running client udsactor')
        client = None
        try:
            client = ipc.ClientIPC(IPC_PORT)
            if 'login' == sys.argv[1]:
                client.sendLogin(sys.argv[2])
                sys.exit(0)
            elif 'logout' == sys.argv[1]:
                client.sendLogout(sys.argv[2])
                sys.exit(0)
            else:
                usage()
        except Exception as e:
            logger.error(e)
    elif len(sys.argv) != 2:
        usage()

    logger.debug('Executing actor')
    daemon = UDSActorSvc()
    if len(sys.argv) == 2:
        if 'start' == sys.argv[1]:
            daemon.start()
        elif 'stop' == sys.argv[1]:
            daemon.stop()
        elif 'restart' == sys.argv[1]:
            daemon.restart()
        else:
            usage()
        sys.exit(0)
    else:
        usage()
