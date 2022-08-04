# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2022 Virtual Cable S.L.U.
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
# pylint: disable=invalid-name
import logging
import os
import tempfile
import typing

import servicemanager

# Valid logging levels, from UDS Broker (uds.core.utils.log).
from .. import loglevel

class LocalLogger:  # pylint: disable=too-few-public-methods
    linux = False
    windows = True
    serviceLogger = False

    logger: typing.Optional[logging.Logger]

    def __init__(self):
        # tempdir is different for "user application" and "service"
        # service wil get c:\windows\temp, while user will get c:\users\XXX\temp
        try:
            logging.basicConfig(
                filename=os.path.join(tempfile.gettempdir(), 'udsactor.log'),
                filemode='a',
                format='%(levelname)s %(asctime)s %(message)s',
                level=logging.DEBUG
            )
        except Exception:
            logging.basicConfig()  # basic init

        self.logger = logging.getLogger('udsactor')
        self.serviceLogger = False

    def log(self, level: int, message: str) -> None:
        # Debug messages are logged to a file
        # our loglevels are 0 (other), 10000 (debug), ....
        # logging levels are 10 (debug), 20 (info)
        # OTHER = logging.NOTSET
        if self.logger:
            self.logger.log(int(level / 1000), message)

        if level < loglevel.ERROR or self.serviceLogger is False:  # Only information and above will be on event log
            return

        # In fact, we have restricted level in windows event log to ERROR or FATAL
        # but left the code for just a case in the future...
        if level < loglevel.WARN:  # Info
            servicemanager.LogInfoMsg(message)
        elif level < loglevel.ERROR:  # WARN
            servicemanager.LogWarningMsg(message)
        else:  # Error & Fatal
            servicemanager.LogErrorMsg(message)
