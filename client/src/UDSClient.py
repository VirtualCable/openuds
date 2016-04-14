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
from uds.log import logger
from uds import tools
from uds import VERSION

import webbrowser

from UDSWindow import Ui_MainWindow

class RetryException(Exception):
    pass

class UDSClient(QtGui.QMainWindow):

    ticket = None
    scrambler = None
    withError = False
    animTimer = None
    anim = 0
    animInc = 1

    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.progressBar.setValue(0)
        self.ui.cancelButton.clicked.connect(self.cancelPushed)

        self.ui.info.setText('Initializing...')

        screen = QtGui.QDesktopWidget().screenGeometry()
        mysize = self.geometry()
        hpos = (screen.width() - mysize.width()) / 2
        vpos = (screen.height() - mysize.height() - mysize.height()) / 2
        self.move(hpos, vpos)

        self.animTimer = QtCore.QTimer()
        QtCore.QObject.connect(self.animTimer, QtCore.SIGNAL('timeout()'), self.updateAnim)

        self.activateWindow()

        self.startAnim()


    def closeWindow(self):
        self.close()

    def processError(self, data):
        if 'error' in data:
            # QtGui.QMessageBox.critical(self, 'Request error {}'.format(data.get('retryable', '0')), data['error'], QtGui.QMessageBox.Ok)
            if data.get('retryable', '0') == '1':
                raise RetryException(data['error'])

            raise Exception(data['error'])
            # QtGui.QMessageBox.critical(self, 'Request error', rest.data['error'], QtGui.QMessageBox.Ok)
            # self.closeWindow()
            # return

    def showError(self, e):
        self.stopAnim()
        self.ui.progressBar.setValue(100)
        self.ui.info.setText('Error')
        QtGui.QMessageBox.critical(self, 'Error', six.text_type(e), QtGui.QMessageBox.Ok)
        self.closeWindow()
        self.withError = True

    def cancelPushed(self):
        self.close()

    @QtCore.pyqtSlot()
    def updateAnim(self):
        self.anim += self.animInc
        if self.anim < 1 or self.anim > 99:
            self.ui.progressBar.invertedAppearance = not self.ui.progressBar.invertedAppearance
            self.animInc = -self.animInc

        self.ui.progressBar.setValue(self.anim)

    def startAnim(self):
        self.ui.progressBar.invertedAppearance = False
        self.anim = 0
        self.animInc = 1
        self.animTimer.start(40)

    def stopAnim(self):
        self.ui.progressBar.invertedAppearance = False
        self.animTimer.stop()

    @QtCore.pyqtSlot()
    def getVersion(self):
        self.req = RestRequest('', self, self.version)
        self.req.get()

    @QtCore.pyqtSlot(dict)
    def version(self, data):
        try:
            self.processError(data)
            self.ui.info.setText('Processing...')

            if data['result']['requiredVersion'] > VERSION:
                QtGui.QMessageBox.critical(self, 'Upgrade required', 'A newer connector version is required.\nA browser will be opened to download it.', QtGui.QMessageBox.Ok)
                webbrowser.open(data['result']['downloadUrl'])
                self.closeWindow()
                return
            self.getTransportData()

        except RetryException as e:
            self.ui.info.setText(six.text_type(e))
            QtCore.QTimer.singleShot(1000, self.getVersion)

        except Exception as e:
            self.showError(e)


    @QtCore.pyqtSlot()
    def getTransportData(self):
        self.req = RestRequest('/{}/{}'.format(self.ticket, self.scrambler), self, self.transportDataReceived, params={'hostname': tools.getHostName(), 'version': VERSION})
        self.req.get()


    @QtCore.pyqtSlot(dict)
    def transportDataReceived(self, data):
        logger.debug('Transport data received')
        try:
            self.processError(data)

            script = data['result'].decode('base64').decode('bz2')

            self.stopAnim()

            if 'darwin' in sys.platform:
                self.showMinimized()

            QtCore.QTimer.singleShot(3000, self.endScript)
            self.hide()

            six.exec_(script, globals(), {'parent': self})

        except RetryException as e:
            self.ui.info.setText(six.text_type(e) + ', retrying access...')
            # Retry operation in ten seconds
            QtCore.QTimer.singleShot(10000, self.getTransportData)

        except Exception as e:
            logger.exception('Got exception executing script:')
            self.showError(e)

    def endScript(self):
        # After running script, wait for stuff
        try:
            tools.waitForTasks()
        except Exception:
            pass

        try:
            tools.unlinkFiles()
        except Exception:
            pass

        try:
            tools.execBeforeExit()
        except Exception:
            pass

        self.closeWindow()

    def start(self):
        '''
        Starts proccess by requesting version info
        '''
        self.ui.info.setText('Initializing...')
        QtCore.QTimer.singleShot(100, self.getVersion)


def done(data):
    QtGui.QMessageBox.critical(None, 'Notice', six.text_type(data.data), QtGui.QMessageBox.Ok)
    sys.exit(0)

# Ask user to aprobe endpoint
def approveHost(host, parentWindow=None):
    settings = QtCore.QSettings()
    settings.beginGroup('endpoints')

    approved = settings.value(host, False).toBool()

    errorString = '<p>The host <b>{}</b> needs to be approve:</p>'.format(host)
    errorString += '<p>Only approve UDS servers that you trust to avoid security issues.</p>'

    if approved or QtGui.QMessageBox.warning(parentWindow, 'ACCESS Warning', errorString, QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) == QtGui.QMessageBox.Yes:
        settings.setValue(host, True)
        approved = True

    settings.endGroup()
    return approved

if __name__ == "__main__":
    logger.debug('Initializing connector')
    # Initialize app
    app = QtGui.QApplication(sys.argv)

    # Set several info for settings
    QtCore.QCoreApplication.setOrganizationName('Virtual Cable S.L.U.')
    QtCore.QCoreApplication.setApplicationName('UDS Connector')

    if 'darwin' not in sys.platform:
        logger.debug('Mac OS *NOT* Detected')
        app.setStyle('plastique')

    if six.PY3 is False:
        logger.debug('Fixing threaded execution of commands')
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    # First parameter must be url
    try:
        uri = sys.argv[1]
        logger.debug('URI: {}'.format(uri))
        if uri[:6] != 'uds://' and uri[:7] != 'udss://':
            raise Exception()

        ssl = uri[3] == 's'
        host, UDSClient.ticket, UDSClient.scrambler = uri.split('//')[1].split('/')
        logger.debug('ssl: {}, host:{}, ticket:{}, scrambler:{}'.format(ssl, host, UDSClient.ticket, UDSClient.scrambler))

    except Exception:
        logger.debug('Detected execution without valid URI, exiting')
        QtGui.QMessageBox.critical(None, 'Notice', 'This program is designed to be used by UDS', QtGui.QMessageBox.Ok)
        sys.exit(1)

    # Setup REST api endpoint
    RestRequest.restApiUrl = '{}://{}/rest/client'.format(['http', 'https'][ssl], host)
    logger.debug('Setting requert URL to {}'.format(RestRequest.restApiUrl))
    # RestRequest.restApiUrl = 'https://172.27.0.1/rest/client'

    try:
        logger.debug('Starting execution')

        # Approbe before going on
        if approveHost(host) is False:
            raise Exception('Host {} was not approved'.format(host))

        win = UDSClient()
        win.show()


        win.start()

        exitVal = app.exec_()
        logger.debug('Execution finished correctly')

    except Exception as e:
        logger.exception('Got an exception executing client:')
        exitVal = 128
        QtGui.QMessageBox.critical(None, 'Error', six.text_type(e), QtGui.QMessageBox.Ok)

    logger.debug('Exiting')
    sys.exit(exitVal)

    # Build base REST

    # v = RestRequest('', done)
    # v.get()

    # sys.exit(1)

    # myapp = UDSConfigDialog(cfg)
    # myapp.show()
