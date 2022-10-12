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
# pylint: disable=invalid-name
import os
import tempfile
import logging
import typing

# Basically, same logger as in linux, 
class LocalLogger:  
    linux = False
    windows = False
    serviceLogger = False

    logger: typing.Optional[logging.Logger]

    def __init__(self) -> None:
        # Try to open logger at /var/log path
        # If it fails (access denied normally), will try to open one at user's home folder, and if
        # agaim it fails, open it at the tmpPath
        for logDir in ('/var/log', os.path.expanduser('~'), tempfile.gettempdir()):
            try:
                fname = os.path.join(logDir, 'udsactor.log')
                logging.basicConfig(
                    filename=fname,
                    filemode='a',
                    format='%(levelname)s %(asctime)s %(message)s',
                    level=logging.DEBUG
                )
                self.logger = logging.getLogger('udsactor')
                os.chmod(fname, 0o0600)
                return
            except Exception:  # nosec: B110: we don't care about exceptions here
                # ignore and try next one
                pass

        # Logger can't be set
        self.logger = None

    def log(self, level: int, message: str) -> None:
        # Debug messages are logged to a file
        # our loglevels are 0 (other), 10000 (debug), ....
        # logging levels are 10 (debug), 20 (info)
        # OTHER = logging.NOTSET
        if self.logger:
            self.logger.log(int(level / 1000), message)
