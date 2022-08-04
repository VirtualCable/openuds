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
# pylint: disable=invalid-name
import traceback
import sys
import typing

if sys.platform == 'win32':
    from .windows.log import LocalLogger
elif sys.platform == 'darwin':
    from .macos.log import LocalLogger
else:
    from .linux.log import LocalLogger

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import rest

# Valid logging levels, from UDS Broker (uds.core.utils.log)
from .loglevel import OTHER, DEBUG, INFO, WARN, ERROR, FATAL

class Logger:
    remoteLogger: typing.Optional['rest.UDSServerApi']
    own_token: str
    logLevel: int
    localLogger: LocalLogger

    def __init__(self) -> None:
        self.logLevel = INFO
        self.localLogger = LocalLogger()
        self.remoteLogger = None
        self.own_token = ''  # nosec: This is no password at all

    def setLevel(self, level: typing.Union[str, int]) -> None:
        '''
        Sets log level filter (minimum level required for a log message to be processed)
        :param level: Any message with a level below this will be filtered out
        '''
        self.logLevel = int(level)  # Ensures level is an integer or fails

    def setRemoteLogger(self, remoteLogger: 'rest.UDSServerApi', own_token: str) -> None:
        self.remoteLogger = remoteLogger
        self.own_token = own_token

    def enableServiceLogger(self):
        if self.localLogger.windows:
            self.localLogger.serviceLogger = True

    def log(self, level: typing.Union[str, int], message: str, *args) -> None:
        level = int(level)
        if level < self.logLevel:  # Skip not wanted messages
            return

        msg = message % args
        # If remote logger is available, notify message to it (except DEBUG messages OFC)
        try:
            if self.remoteLogger and level >= DEBUG:
                self.remoteLogger.log(self.own_token, level, msg)
        except Exception as e:
            self.localLogger.log(DEBUG, 'Log to broker: {}'.format(e))

        self.localLogger.log(level, msg)

    def debug(self, message: str, *args) -> None:
        self.log(DEBUG, message, *args)

    def warn(self, message: str, *args) -> None:
        self.log(WARN, message, *args)

    def info(self, message: str, *args) -> None:
        self.log(INFO, message, *args)

    def error(self, message: str, *args) -> None:
        self.log(ERROR, message, *args)

    def fatal(self, message: str, *args) -> None:
        self.log(FATAL, message, *args)

    def exception(self) -> None:
        try:
            tb = traceback.format_exc()
        except Exception:
            tb = '(could not get traceback!)'

        self.log(DEBUG, tb)

    def flush(self) -> None:
        pass


logger = Logger()
