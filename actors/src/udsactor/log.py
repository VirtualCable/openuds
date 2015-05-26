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

import traceback
import sys
import six

if sys.platform == 'win32':
    from udsactor.windows.log import LocalLogger  # @UnusedImport
else:
    from udsactor.linux.log import LocalLogger  # @Reimport

# Valid logging levels, from UDS Broker (uds.core.utils.log)
OTHER, DEBUG, INFO, WARN, ERROR, FATAL = (10000 * (x + 1) for x in six.moves.xrange(6))  # @UndefinedVariable


class Logger(object):
    def __init__(self):
        self.logLevel = INFO
        self.logger = LocalLogger()
        self.remoteLogger = None

    def setLevel(self, level):
        '''
        Sets log level filter (minimum level required for a log message to be processed)
        :param level: Any message with a level below this will be filtered out
        '''
        self.logLevel = int(level)  # Ensures level is an integer or fails

    def setRemoteLogger(self, remoteLogger):
        self.remoteLogger = remoteLogger

    def log(self, level, message):
        if level < self.logLevel:  # Skip not wanted messages
            return

        # If remote logger is available, notify message to it
        try:
            if self.remoteLogger is not None and self.remoteLogger.isConnected and level >= INFO:
                self.remoteLogger.log(level, message)
        except Exception as e:
            self.logger.log(FATAL, 'Error notifying log to broker: {}'.format(e.message))

        self.logger.log(level, message)

    def debug(self, message):
        self.log(DEBUG, message)

    def warn(self, message):
        self.log(WARN, message)

    def info(self, message):
        self.log(INFO, message)

    def error(self, message):
        self.log(ERROR, message)

    def fatal(self, message):
        self.log(FATAL, message)

    def exception(self):
        try:
            tb = traceback.format_exc()
        except Exception:
            tb = '(could not get traceback!)'

        self.log(DEBUG, tb)

    def flush(self):
        pass


logger = Logger()
