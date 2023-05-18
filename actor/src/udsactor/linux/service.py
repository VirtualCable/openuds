# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2023 Virtual Cable S.L.
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
@author: Alexander Burmatov,  thatman at altlinux dot org
'''
import signal
import copy
import typing

from . import daemon
from . import operations

from ..log import logger
from ..service import CommonService

try:
    from prctl import set_proctitle  # type: ignore
except ImportError:  # Platform may not include prctl, so in case it's not available, we let the "name" as is
    def set_proctitle(_):
        pass

class UDSActorSvc(daemon.Daemon, CommonService):
    _sensibleDataCleanable: bool = False

    def __init__(self) -> None:
        daemon.Daemon.__init__(self, '/run/udsactor.pid')
        CommonService.__init__(self)

        # Captures signals so we can stop gracefully
        signal.signal(signal.SIGINT, self.markForExit)
        signal.signal(signal.SIGTERM, self.markForExit)

    def markForExit(self, signum, frame) -> None:  # pylint: disable=unused-argument
        self._isAlive = False

    def canCleanSensibleData(self) -> bool:
        return self._sensibleDataCleanable

    def joinDomain(  # pylint: disable=unused-argument, too-many-arguments
        self, name: str, custom: typing.Mapping[str, typing.Any]
    ) -> None:
    
        self._sensibleDataCleanable = custom.get('isPersistent', False)

        self.rename(name)

        logger.debug('Starting joining domain %s with name %s', custom.get('domain', ''), name)
        operations.joinDomain(name, custom)

    def finish(self) -> None:
        try:
            if self._cfg.config and self._cfg.config.os and self._cfg.config.os.custom:
                osData = self._cfg.config.os
                custom = self._cfg.config.os.custom
                if osData.action == 'rename_ad' and custom.get('isPersistent', False):
                    operations.leaveDomain(
                        custom.get('ad', ''),
                        custom.get('username', ''),
                        custom.get('password', ''),
                        custom.get('clientSoftware', ''),
                        custom.get('serverSoftware', ''),
                    )
        except Exception as e:
            logger.error(f'Got exception operating machine: {e}')
        super().finish()

    def run(self) -> None:
        logger.debug('Running Daemon: {}'.format(self._isAlive))
        set_proctitle('UDSActorDaemon')

        # Linux daemon will continue running unless something is requested to
        # Unmanaged services does not initializes "on start", but rather when user logs in (because userservice does not exists "as such" before that)
        if self.isManaged():
            if not self.initialize():
                self.finish()
                return # Stop daemon if initializes told to do so

            # logger.debug('Initialized, setting ready')
            # Initialization is done, set machine to ready for UDS, communicate urls, etc...
            self.setReady()
        else:
            if not self.initializeUnmanaged():
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
