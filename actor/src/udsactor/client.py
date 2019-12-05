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
import threading
import time
import typing

from PyQt5.QtWidgets import QApplication, QMessageBox

from . import rest
from . import tools
from . import platform

from .log import logger

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import types

class UDSActorClient(threading.Thread):
    _running: bool
    _forceLogoff: bool
    _qApp: QApplication
    _api: rest.UDSClientApi

    def __init__(self, qApp: QApplication):
        super().__init__()

        self._api = rest.UDSClientApi()  # Self initialized
        self._qApp = qApp
        self._running = False
        self._forceLogoff = False

    def run(self):
        self._running = True

        # Notify loging and mark it
        self._api.login(platform.operations.getCurrentUser())

        while self._running:
            time.sleep(1.1)  # Sleep between loop iteration

        self._api.logout(platform.operations.getCurrentUser())

        # Notify Qapllication to exit
        QApplication.quit()

        if self._forceLogoff:
            platform.operations.loggoff()

    def _showMessage(self, message: str) -> None:
        QMessageBox.information(None, 'Message', message)

    def stop(self) -> None:
        logger.debug('Stopping client Service')
        self._running = False

    def logout(self) -> typing.Any:
        self._forceLogoff = True
        self._running = False
        return 'ok'

    def message(self, msg: str) -> typing.Any:
        threading.Thread(target=self._showMessage, args=(msg,)).start()
        return 'ok'

    def screenshot(self) -> typing.Any:
        pass

    def script(self, script: str) -> typing.Any:
        tools.ScriptExecutorThread(script).start()
        return 'ok'
