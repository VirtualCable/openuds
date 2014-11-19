#!/usr/bin/env python
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

import sys
from PyQt4 import QtGui
from PyQt4 import QtCore
import cPickle
from udsactor import ipc
from udsactor import utils
from udsactor.log import logger
from udsactor.service import IPC_PORT


class MessagesProcessor(QtCore.QThread):

    logoff = QtCore.pyqtSignal(name='logoff')
    displayMessage = QtCore.pyqtSignal(QtCore.QString, name='displayMessage')
    script = QtCore.pyqtSignal(QtCore.QString, name='script')
    exit = QtCore.pyqtSignal(name='exit')
    information = QtCore.pyqtSignal(dict, name='information')

    def __init__(self):
        super(self.__class__, self).__init__()
        try:
            self.ipc = ipc.ClientIPC(IPC_PORT)
            self.ipc.start()
        except Exception:
            self.ipc = None

        self.running = False

    def stop(self):
        self.running = False
        if self.ipc:
            self.ipc.stop()

    def requestInformation(self):
        if self.ipc:
            info = self.ipc.requestInformation()
            logger.debug('Request information: {}'.format(info))

    def run(self):
        if self.ipc is None:
            return
        self.running = True
        while self.running and self.ipc.running:
            try:
                msg = self.ipc.getMessage()
                if msg is None:
                    break
                msgId, data = msg
                logger.debug('Got Message on User Space: {}:{}'.format(msgId, data))
                if msgId == ipc.MSG_MESSAGE:
                    self.displayMessage.emit(QtCore.QString.fromUtf8(data))
                elif msgId == ipc.MSG_LOGOFF:
                    self.logoff.emit()
                elif msgId == ipc.MSG_SCRIPT:
                    self.script.emit(QtCore.QString.fromUtf8(data))
                elif msgId == ipc.MSG_INFORMATION:
                    self.information.emit(cPickle.loads(data))
            except Exception as e:
                try:
                    logger.error('Got error on IPC thread {}'.format(utils.exceptionToMessage(e)))
                except:
                    logger.error('Got error on IPC thread (an unicode error??)')

        if self.ipc.running is False and self.running is True:
            logger.warn('Lost connection with Service, closing program')

        self.exit.emit()


class UDSSystemTray(QtGui.QSystemTrayIcon):
    def __init__(self, app_, parent=None):
        self.app = app_

        style = app.style()
        icon = QtGui.QIcon(style.standardPixmap(QtGui.QStyle.SP_DesktopIcon))

        QtGui.QSystemTrayIcon.__init__(self, icon, parent)
        self.menu = QtGui.QMenu(parent)
        exitAction = self.menu.addAction("Exit")
        exitAction.triggered.connect(self.quit)
        self.setContextMenu(self.menu)
        self.ipc = MessagesProcessor()
        self.ipc.start()

        self.ipc.displayMessage.connect(self.displayMessage)
        self.ipc.exit.connect(self.quit)
        self.ipc.script.connect(self.executeScript)
        self.ipc.logoff.connect(self.loggof)
        self.ipc.information.connect(self.information)

        # Pre generate a request for information (general parameters) to daemon/service
        self.ipc.requestInformation()

        self.counter = 0

    def displayMessage(self, message):
        self.counter += 1
        print(message.toUtf8(), '--', self.counter)

    def executeScript(self, message):
        self.counter += 1
        print(message.toUtf8(), '--', self.counter)

    def loggof(self):
        self.counter += 1
        print("Loggof --", self.counter)

    def information(self, info):
        self.counter += 1
        print("Information:", info, '--', self.counter)

    def quit(self):
        self.ipc.stop()

        self.app.quit()

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    if not QtGui.QSystemTrayIcon.isSystemTrayAvailable():
        QtGui.QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    trayIcon = UDSSystemTray(app)

    trayIcon.show()
    sys.exit(app.exec_())
