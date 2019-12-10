#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Virtual Cable S.L.
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
import sys
import os

import PyQt5  # pylint: disable=unused-import
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from udsactor.log import logger, DEBUG
from udsactor.client import UDSActorClient

class UDSClientQApp(QApplication):
    _app: UDSActorClient
    _initialized: bool

    def __init__(self, args) -> None:
        super().__init__(args)

        # This will be invoked on session close
        self.commitDataRequest.connect(self.end)  # Will be invoked on session close, to gracely close app

        # Execute backgroup thread for actions
        self._app = UDSActorClient(self)

    def init(self) -> None:
        # Notify loging and mark it
        logger.debug('Starting APP')
        self._app.start()
        self._initialized = True

    def end(self, sessionManager=None) -> None:
        if not self._initialized:
            return

        self._initialized = False

        logger.debug('Stopping app thread')
        self._app.stop()

        self._app.join()

if __name__ == "__main__":
    logger.setLevel(DEBUG)

    if 'linux' in sys.platform:
        os.environ['QT_X11_NO_MITSHM'] = '1'

    logger.info('Started UDS Client Actor')

    QApplication.setQuitOnLastWindowClosed(False)

    qApp = UDSClientQApp(sys.argv)

    # Crate a timer, so we can check signals from time to time by executing python interpreter
    # Note: Signals are only checked on python code execution, so we create a
    timer = QTimer(qApp)
    timer.start(1000)
    timer.timeout.connect(lambda *a: None)

    qApp.init()
    qApp.exec_()
    qApp.end()

    logger.debug('Exiting...')
