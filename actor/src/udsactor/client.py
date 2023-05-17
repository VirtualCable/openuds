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
import datetime
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
    from PyQt5.QtWidgets import QMainWindow

class UDSClientQApp(QApplication):
    _app: 'UDSActorClient'
    _initialized: bool
    _mainWindow: typing.Optional['QMainWindow']

    message = pyqtSignal(str, name='message')

    def __init__(self, args) -> None:
        super().__init__(args)

        self._mainWindow = None
        self._initialized = False

        # This will be invoked on session close
        self.commitDataRequest.connect(self.end)  # type: ignore  # Will be invoked on session close, to gracely close app
        # self.aboutToQuit.connect(self.end)
        self.message.connect(self.showMessage)  # type: ignore  # there are problems with Pylance and connects on PyQt5... :)

        # Execute backgroup thread for actions
        self._app = UDSActorClient(self)

    def init(self) -> None:
        # Notify loging and mark it
        logger.debug('Starting APP')

        if self._mainWindow:
            self._mainWindow.hide()

        self._app.start()
        self._initialized = True

    def end(self, sessionManager=None) -> None:  # pylint: disable=unused-argument
        if not self._initialized:
            return

        self._initialized = False

        logger.debug('Stopping app thread')
        self._app.stop()

        self._app.join()

    def showMessage(self, message: str) -> None:
        QMessageBox.information(None, 'Message', message)  # type: ignore

    def setMainWindow(self, mw: 'QMainWindow'):
        self._mainWindow = mw


class UDSActorClient(threading.Thread):  # pylint: disable=too-many-instance-attributes
    _running: bool
    _forceLogoff: bool
    _extraLogoff: str
    _qApp: UDSClientQApp
    _listener: client.HTTPServerThread
    _loginInfo: typing.Optional['types.LoginResultInfoType']
    _notified: bool
    _notifiedDeadline: bool
    _sessionStartTime: datetime.datetime
    api: rest.UDSClientApi

    def __init__(self, qApp: QApplication):
        super().__init__()

        self.api = rest.UDSClientApi()  # Self initialized
        self._qApp = typing.cast(UDSClientQApp, qApp)
        self._running = False
        self._forceLogoff = False
        self._extraLogoff = ''
        self._listener = client.HTTPServerThread(self)
        self._loginInfo = None
        self._notified = False
        self._notifiedDeadline = False

        # Capture stop signals..
        logger.debug('Setting signals...')
        signal.signal(signal.SIGINT, self.stopSignal)
        signal.signal(signal.SIGTERM, self.stopSignal)

    def stopSignal(self, signum, frame) -> None:  # pylint: disable=unused-argument
        logger.info('Stop signal received')
        self.stop()

    def checkDeadLine(self):
        if self._loginInfo is None or not self._loginInfo.dead_line:  # No deadline check
            return

        remainingTime = self._loginInfo.dead_line - (datetime.datetime.now() - self._sessionStartTime).total_seconds()
        logger.debug('Remaining time: {}'.format(remainingTime))

        if not self._notifiedDeadline and remainingTime < 300:  # With five minutes, show a warning message
            self._notifiedDeadline = True
            self._showMessage('Your session will expire in less that 5 minutes. Please, save your work and disconnect.')
            return

        if remainingTime <= 0:
            logger.debug('Session dead line reached. Logging out')
            self._running = False
            self._forceLogoff = True

    def checkIdle(self) -> None:
        if self._loginInfo is None or not self._loginInfo.max_idle:  # No idle check
            return

        idleTime = platform.operations.getIdleDuration()
        remainingTime = self._loginInfo.max_idle - idleTime

        logger.debug('Idle: %s Remaining: %s', idleTime, remainingTime)

        if remainingTime > 120:  # Reset show Warning dialog if we have more than 5 minutes left
            self._notified = False
            return

        if not self._notified and remainingTime < 120:  # With two minutes, show a warning message
            self._notified = True
            self._showMessage('You have been idle for too long. The session will end if you don\'t resume operations.')

        if remainingTime <= 0:
            logger.info('User has been idle for too long, exiting from session')
            self._extraLogoff = ' (idle: {} vs {})'.format(int(idleTime), self._loginInfo.max_idle)
            self._running = False
            self._forceLogoff = True

    def run(self) -> None:
        logger.debug('UDS Actor thread')
        self._listener.start()  # async listener for service
        self._running = True

        self._sessionStartTime = datetime.datetime.now()

        time.sleep(0.4)  # Wait a bit before sending login

        try:
            # Notify loging and mark it
            user, sessionType = platform.operations.getCurrentUser(), platform.operations.getSessionType()
            self._loginInfo = self.api.login(user, sessionType)

            if self._loginInfo.max_idle:
                platform.operations.initIdleDuration(self._loginInfo.max_idle)

            while self._running:
                # Check Idle & dead line
                self.checkIdle()
                self.checkDeadLine()

                time.sleep(1.22)  # Sleeps between loop iterations

            self.api.logout(user + self._extraLogoff, sessionType)
            logger.info('Notified logout for %s (%s)', user, sessionType)  # Log logout

            # Clean up login info
            self._loginInfo = None
        except Exception as e:
            logger.error('Error on client loop: %s', e)

        self._listener.stop() # async listener for service

        # Notify exit to qt
        QApplication.quit()

        if self._forceLogoff:
            time.sleep(1.3)  # Wait a bit before forcing logoff
            platform.operations.loggoff()

    def _showMessage(self, message: str) -> None:
        self._qApp.message.emit(message)   # type: ignore  # there are problems with Pylance and connects on PyQt5... :)

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
        pixmap: 'QPixmap' = self._qApp.primaryScreen().grabWindow(0)  # type: ignore
        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, 'PNG')
        buffer.close()
        scrBase64 = bytes(ba.toBase64()).decode()    # type: ignore  # there are problems with Pylance and connects on PyQt5... :)
        logger.debug('Screenshot length: %s', len(scrBase64))
        return scrBase64  # 'result' of JSON will contain base64 of screen

    def script(self, script: str) -> typing.Any:
        tools.ScriptExecutorThread(script).start()
        return 'ok'
