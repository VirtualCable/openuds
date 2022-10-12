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

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import typing
import signal

from ..log import logger
from ..service import CommonService


class UDSActorSvc(CommonService):
    def __init__(self) -> None:
        CommonService.__init__(self)

        # Captures signals so we can stop gracefully
        signal.signal(signal.SIGINT, self.markForExit)
        signal.signal(signal.SIGTERM, self.markForExit)

    def markForExit(self, signum, frame) -> None:  # pylint: disable=unused-argument
        self._isAlive = False

    def joinDomain(  # pylint: disable=unused-argument, too-many-arguments
            self,
            name: str,
            domain: str,
            ou: str,
            account: str,
            password: str
        ) -> None:
        pass  # Not implemented for unmanaged machines

    def rename(
        self,
        name: str,
        userName: typing.Optional[str] = None,
        oldPassword: typing.Optional[str] = None,
        newPassword: typing.Optional[str] = None,
    ) -> None:
        pass  # Not implemented for unmanaged machines

    def run(self) -> None:
        logger.debug('Running Daemon: {}'.format(self._isAlive))

        # Linux daemon will continue running unless something is requested to
        # Unmanaged services does not initializes "on start", but rather when user logs in (because userservice does not exists "as such" before that)
        if self.isManaged():  # Currently, managed is not implemented for UDS on M
            logger.error('Managed machines not supported on MacOS')
            # Wait a bit, this is mac os and will be run by launchd
            # If the daemon shuts down too quickly, launchd may think it is a crash.
            self.doWait(10000)

            self.finish()
            return # Stop daemon if initializes told to do so
        if not self.initializeUnmanaged():
            # Wait a bit, this is mac os and will be run by launchd
            # If the daemon shuts down too quickly, launchd may think it is a crash.
            self.doWait(10000)
            self.finish()
            return

        # Start listening for petitions
        self.startHttpServer()

        # *********************
        # * Main Service loop *
        # *********************
        # Counter used to check ip changes only once every 10 seconds, for
        # example
        counter = 0
        while self._isAlive:
            counter += 1
            try:
                if counter % 5 == 0:
                    self.loop()
            except Exception as e:
                logger.error('Got exception on main loop: %s', e)
            # In milliseconds, will break
            self.doWait(1000)

        self.finish()
