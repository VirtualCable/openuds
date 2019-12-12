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
import threading
import time
import signal
import typing

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QByteArray, QBuffer, QIODevice, pyqtSignal

from . import rest
from . import tools
from . import platform

from .log import logger

from .http import client

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from . import types
    from PyQt5.QtGui import QPixmap


class UDSClientQApp(QApplication):
    _app: 'UDSActorClient'
    _initialized: bool

    message = pyqtSignal(str, name='message')

    def __init__(self, args) -> None:
        super().__init__(args)

        # This will be invoked on session close
        self.commitDataRequest.connect(self.end)  # Will be invoked on session close, to gracely close app
        self.aboutToQuit.connect(self.end)


        self.message.connect(self.showMessage)

        # Execute backgroup thread for actions
        self._app = UDSActorClient(self)

    def init(self) -> None:
        # Notify loging and mark it
        logger.debug('Starting APP')
        self._app.start()

        self.aboutToQuit.connect(lambda: logger.debug('About to quit'))

        self._initialized = True

    def end(self, sessionManager=None) -> None:
        logger.debug('Stopping App')
        if not self._initialized:
            return

        self._initialized = False

        logger.debug('Stopping app thread')
        self._app.stop()

        self._app.join()

    def showMessage(self, message: str) -> None:
        QMessageBox.information(None, 'Message', message)


class UDSActorClient(threading.Thread):
    _running: bool
    _forceLogoff: bool
    _qApp: UDSClientQApp
    api: rest.UDSClientApi
    _listener: client.HTTPServerThread

    def __init__(self, qApp: QApplication):
        super().__init__()

        self.api = rest.UDSClientApi()  # Self initialized
        self._qApp = qApp
        self._running = False
        self._forceLogoff = False
        self._listener = client.HTTPServerThread(self)

        # Capture stop signals..
        logger.debug('Setting signals...')
        signal.signal(signal.SIGINT, self.stopSignal)
        signal.signal(signal.SIGTERM, self.stopSignal)

    def stopSignal(self, signum, frame) -> None:  # pylint: disable=unused-argument
        logger.info('Stop signal received')
        self.stop()

    def run(self):
        logger.debug('UDS Actor thread')
        self._listener.start()  # async listener for service
        self._running = True

        time.sleep(0.4)  # Wait a bit before sending login

        try:
            # Notify loging and mark it
            if platform.name != 'win32':  # On win32, SENS will send login/logouts
                self.api.login(platform.operations.getCurrentUser())

            while self._running:
                time.sleep(1.1)  # Sleeps between loop iterations

            if platform.name != 'win32':  # On win32, SENS will send login/logouts
                self.api.logout(platform.operations.getCurrentUser())
        except Exception as e:
            logger.error('Error on client loop: %s', e)

        self._listener.stop() # async listener for service

        # Notify exit to qt
        QApplication.quit()

        if self._forceLogoff:
            platform.operations.loggoff()

    def _showMessage(self, message: str) -> None:
        self._qApp.message.emit(message)

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
        '''
        On windows, an RDP session with minimized screen will render "black screen"
        So only when user is using RDP connection will return an "actual" screenshot
        '''
        pixmap: 'QPixmap' = self._qApp.primaryScreen().grabWindow(0)
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, 'PNG')
        buffer.close()
        scrBase64 = bytes(ba.toBase64()).decode()
        logger.debug('Screenshot length: %s', len(scrBase64))
        return scrBase64  # 'result' of JSON will contain base64 of screen

    def script(self, script: str) -> typing.Any:
        tools.ScriptExecutorThread(script).start()
        return 'ok'
