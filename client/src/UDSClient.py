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
from PyQt4 import QtCore, QtGui
import six

from uds.rest import RestRequest
from uds.forward import forward
from uds import tools

import webbrowser
import time

from UDSWindow import Ui_MainWindow

# Client connector version
VERSION = '1.7.5'


class UDSClient(QtGui.QMainWindow):

    ticket = None
    scrambler = None
    withError = False

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.progressBar.setValue(0)
        self.ui.cancelButton.clicked.connect(self.cancelPushed)

        self.ui.info.setText('Initializing...')

        self.activateWindow()

    def closeWindow(self):
        self.close()

    def processError(self, data):
        if 'error' in data:
            raise Exception(data['error'])
            # QtGui.QMessageBox.critical(self, 'Request error', rest.data['error'], QtGui.QMessageBox.Ok)
            # self.closeWindow()
            # return

    def showError(self, e):
        self.ui.progressBar.setValue(100)
        self.ui.info.setText('Error')
        QtGui.QMessageBox.critical(self, 'Error', six.text_type(e), QtGui.QMessageBox.Ok)
        self.closeWindow()
        self.withError = True

    def cancelPushed(self):
        self.close()

    @QtCore.pyqtSlot()
    def getVersion(self):
        self.req = RestRequest('', self, self.version)
        self.req.get()

    @QtCore.pyqtSlot(dict)
    def version(self, data):
        try:
            self.ui.progressBar.setValue(10)

            self.processError(data)

            self.ui.info.setText('Processing...')

            if data['result']['requiredVersion'] > VERSION:
                QtGui.QMessageBox.critical(self, 'Upgrade required', 'A newer connector version is required.\nA browser will be opened to download it.', QtGui.QMessageBox.Ok)
                webbrowser.open(data['result']['downloadUrl'])
                self.closeWindow()
                return

            self.req = RestRequest('/{}/{}'.format(self.ticket, self.scrambler), self, self.transportDataReceived)
            self.req.get()

        except Exception as e:
            self.showError(e)

    @QtCore.pyqtSlot(dict)
    def transportDataReceived(self, data):
        try:
            self.ui.progressBar.setValue(20)
            self.processError(data)

            script = data['result'].decode('base64').decode('bz2')

            six.exec_(script, globals(), {'parent': self})
            self.showMinimized()

            # After running script, wait for stuff
            try:
                tools.waitForTasks()
            except Exception:
                pass

            time.sleep(3)
            try:
                tools.unlinkFiles()
            except Exception:
                pass

            try:
                tools.execBeforeExit()
            except Exception:
                pass

            self.closeWindow()
        except Exception as e:
            self.showError(e)

    def start(self):
        '''
        Starts proccess by requesting version info
        '''
        self.ui.info.setText('Initializing...')
        QtCore.QTimer.singleShot(100, self.getVersion)


def done(data):
    QtGui.QMessageBox.critical(None, 'Notice', six.text_type(data.data), QtGui.QMessageBox.Ok)
    sys.exit(0)

if __name__ == "__main__":
    # Initialize app
    app = QtGui.QApplication(sys.argv)

    # Set several info for settings
    QtCore.QCoreApplication.setOrganizationName('Virtual Cable S.L.U.')
    QtCore.QCoreApplication.setApplicationName('UDS Connector')

    app.setStyle(QtGui.QStyleFactory.create('plastique'))

    if six.PY3 is False:
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    # First parameter must be url
    try:
        uri = sys.argv[1]
        if uri[:6] != 'uds://' and uri[:7] != 'udss://':
            raise Exception()

        ssl = uri[3] == 's'
        host, UDSClient.ticket, UDSClient.scrambler = uri.split('//')[1].split('/')

    except Exception:
        QtGui.QMessageBox.critical(None, 'Notice', 'This program is designed to be used by UDS', QtGui.QMessageBox.Ok)
        sys.exit(1)

    # Setup REST api endpoint
    RestRequest.restApiUrl = '{}://{}/rest/client'.format(['http', 'https'][ssl], host)
    # RestRequest.restApiUrl = 'https://172.27.0.1/rest/client'

    try:
        win = UDSClient()
        win.show()
        win.start()

        exitVal = app.exec_()

    except Exception as e:
        QtGui.QMessageBox.critical(None, 'Error', six.text_type(e), QtGui.QMessageBox.Ok)

    sys.exit(exitVal)

    # Build base REST

    # v = RestRequest('', done)
    # v.get()

    # sys.exit(1)

    # myapp = UDSConfigDialog(cfg)
    # myapp.show()
