#!/usr/bin/env python2.7
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
from PyQt4 import QtGui  # @UnresolvedImport
from PyQt4 import QtCore  # @UnresolvedImport
import pickle
import time
import datetime
import signal
from udsactor import ipc
from udsactor import utils
from udsactor.log import logger
from udsactor.service import IPC_PORT
from udsactor import operations
from about_dialog_ui import Ui_UDSAboutDialog
from message_dialog_ui import Ui_UDSMessageDialog
from udsactor.scriptThread import ScriptExecutorThread
from udsactor import VERSION

trayIcon = None

doLogoff = False


def sigTerm(sigNo, stackFrame):
    if trayIcon:
        trayIcon.quit()


# About dialog
class UDSAboutDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.ui = Ui_UDSAboutDialog()
        self.ui.setupUi(self)
        self.ui.VersionLabel.setText("Version " + VERSION)

    def closeDialog(self):
        self.hide()


class UDSMessageDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.ui = Ui_UDSMessageDialog()
        self.ui.setupUi(self)

    def displayMessage(self, message):
        self.ui.message.setText(message)
        self.show()

    def closeDialog(self):
        self.hide()


class MessagesProcessor(QtCore.QThread):

    logoff = QtCore.pyqtSignal(name='logoff')
    displayMessage = QtCore.pyqtSignal(QtCore.QString, name='displayMessage')
    script = QtCore.pyqtSignal(QtCore.QString, name='script')
    exit = QtCore.pyqtSignal(name='exit')
    information = QtCore.pyqtSignal(dict, name='information')

    def __init__(self):
        super(self.__class__, self).__init__()
        # Retries connection for a while
        for _ in range(10):
            try:
                self.ipc = ipc.ClientIPC(IPC_PORT)
                self.ipc.start()
                break
            except Exception:
                logger.debug('IPC Server is not reachable')
                self.ipc = None
                time.sleep(2)

        self.running = False

    def stop(self):
        self.running = False
        if self.ipc:
            self.ipc.stop()

    def isAlive(self):
        return self.ipc is not None

    def requestInformation(self):
        if self.ipc is not None:
            info = self.ipc.requestInformation()
            logger.debug('Request information: {}'.format(info))

    def sendLogin(self, userName):
        if self.ipc:
            self.ipc.sendLogin(userName)

    def sendLogout(self, userName):
        if self.ipc:
            self.ipc.sendLogout(userName)

    def run(self):
        if self.ipc is None:
            return
        self.running = True

        # Wait a bit so we ensure IPC thread is running...
        time.sleep(2)

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
                    self.information.emit(pickle.loads(data))
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

        # style = app.style()
        # icon = QtGui.QIcon(style.standardPixmap(QtGui.QStyle.SP_ComputerIcon))
        icon = QtGui.QIcon(':/images/img/uds.png')

        QtGui.QSystemTrayIcon.__init__(self, icon, parent)
        self.menu = QtGui.QMenu(parent)
        exitAction = self.menu.addAction("About")
        exitAction.triggered.connect(self.about)
        self.setContextMenu(self.menu)
        self.ipc = MessagesProcessor()
        self.sessionStart = datetime.datetime.now()
        self.maxIdleTime = None
        self.showIdleWarn = True
        self.maxSessionTime = None
        self.showMaxSessionWarn = True
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.checkTimers)

        if self.ipc.isAlive() is False:
            raise Exception('No connection to service, exiting.')

        self.stopped = False

        self.ipc.displayMessage.connect(self.displayMessage)
        self.ipc.exit.connect(self.quit)
        self.ipc.script.connect(self.executeScript)
        self.ipc.logoff.connect(self.logoff)
        self.ipc.information.connect(self.information)

        # Pre generate a request for information (general parameters) to daemon/service
        self.ipc.requestInformation()

        self.aboutDlg = UDSAboutDialog()
        self.msgDlg = UDSMessageDialog()

        self.counter = 0

        self.timer.start(5000)  # Launch idle checking every 5 seconds
        self.graceTimerShots = 6  # Start counting for idle after 30 seconds after login, got on windows some "instant" logout because of idle timer not being reset??

        self.ipc.start()
        # If this is running, it's because he have logged in
        self.ipc.sendLogin(operations.getCurrentUser())

    def checkTimers(self):
        self.checkIdle()
        self.checkMaxSession()

    def checkMaxSession(self):
        if self.maxSessionTime is None or self.maxSessionTime == 0:
            logger.debug('Returning because maxSessionTime is cero')
            return

        remainingTime = self.maxSessionTime - (datetime.datetime.now() - self.sessionStart).total_seconds()
        logger.debug('Remaining time: {}'.format(remainingTime))

        if self.showMaxSessionWarn is True and remainingTime < 300:  # With five minutes, show a warning message
            self.showMaxSessionWarn = False
            self.msgDlg.displayMessage('Your session will expire in less that 5 minutes. Please, save your work and disconnect.')
            return

        if remainingTime <= 0:
            logger.debug('Remaining time is less than cero, exiting')
            self.quit()

    def checkIdle(self):
        if self.maxIdleTime is None:  # No idle check
            return

        if self.graceTimerShots > 0:
            self.graceTimerShots -= 1
            return

        idleTime = operations.getIdleDuration()
        remainingTime = self.maxIdleTime - idleTime

        if remainingTime > 120:  # Reset show Warning dialog if we have more than 5 minutes left
            self.showIdleWarn = True

        logger.debug('User has been idle for: {}'.format(idleTime))

        if self.showIdleWarn is True and remainingTime < 120:  # With two minutes, show a warning message
            self.showIdleWarn = False
            self.msgDlg.displayMessage("You have been idle for too long. The session will end if you don't resume operations")

        if remainingTime <= 0:
            logger.info('User has been idle for too long, notifying Broker that service can be reclaimed')
            self.quit(logoff=True)

    def displayMessage(self, message):
        logger.debug('Displaying message')
        self.msgDlg.displayMessage(message)

    def executeScript(self, script):
        logger.debug('Executing script')
        th = ScriptExecutorThread(script)
        th.start()

    def logoff(self):
        self.counter += 1
        # print("Logofff --", self.counter)

    def information(self, info):
        '''
        Invoked when received information from service
        '''
        logger.info('Got information message: {}'.format(info))
        if 'idle' in info:
            idle = int(info['idle'])
            operations.initIdleDuration(idle)
            self.maxIdleTime = idle
            logger.debug('Set screensaver launching to {}'.format(idle))
        else:
            self.maxIdleTime = None

        if 'maxSession' in info:
            maxSession = int(info['maxSession'])
            # operations.initMaxSession(maxSession)
            self.maxSessionTime = maxSession
            logger.debug('Set maxsession to {}'.format(maxSession))

    def about(self):
        self.aboutDlg.exec_()

    def quit(self, logoff=False):
        global doLogoff
        logger.debug('Quit invoked')
        if self.stopped is False:
            self.stopped = True
            try:
                # If we close Client, send Logoff to Broker
                self.ipc.sendLogout(operations.getCurrentUser())
                self.timer.stop()
                self.ipc.stop()
            except Exception:
                # May we have lost connection with server, simply exit in that case
                pass

        doLogoff = logoff

        self.app.quit()

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)

    if not QtGui.QSystemTrayIcon.isSystemTrayAvailable():
        # QtGui.QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    # This is important so our app won't close on message windows
    QtGui.QApplication.setQuitOnLastWindowClosed(False)

    try:
        trayIcon = UDSSystemTray(app)
    except Exception:
        logger.error('UDS Service is not running, or it can\'t contact with UDS Server. User Tools stopped')
        sys.exit(1)

    # Sets a default idle duration, but will not be used unless idle is notified from server
    operations.initIdleDuration(3600 * 10)

    trayIcon.show()

    # Catch kill and logout user :)
    signal.signal(signal.SIGTERM, sigTerm)

    res = app.exec_()

    logger.debug('Exiting')
    trayIcon.quit()

    if doLogoff:
        try:
            time.sleep(1)
            operations.loggoff()  # Invoke log off
        except Exception:
            pass


    sys.exit(res)
