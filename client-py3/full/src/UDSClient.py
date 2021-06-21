#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import sys
import os
import platform
import time
import webbrowser
import threading
import typing

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import QSettings

from uds.rest import RestApi, RetryException, InvalidVersion, UDSException

# Just to ensure there are available on runtime
from uds.forward import forward  # type: ignore
from uds.tunnel import forward as f2  # type: ignore

from uds.log import logger
from uds import tools
from uds import VERSION

from UDSWindow import Ui_MainWindow


class UDSClient(QtWidgets.QMainWindow):

    ticket: str = ''
    scrambler: str = ''
    withError = False
    animTimer: typing.Optional[QtCore.QTimer] = None
    anim: int = 0
    animInverted: bool = False
    api: RestApi

    def __init__(self, api: RestApi, ticket: str, scrambler: str):
        QtWidgets.QMainWindow.__init__(self)
        self.api = api
        self.ticket = ticket
        self.scrambler = scrambler
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)  # type: ignore

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.progressBar.setValue(0)
        self.ui.cancelButton.clicked.connect(self.cancelPushed)

        self.ui.info.setText('Initializing...')

        screen = QtWidgets.QDesktopWidget().screenGeometry()
        mysize = self.geometry()
        hpos = (screen.width() - mysize.width()) // 2
        vpos = (screen.height() - mysize.height() - mysize.height()) // 2
        self.move(hpos, vpos)

        self.animTimer = QtCore.QTimer()
        self.animTimer.timeout.connect(self.updateAnim)  # type: ignore
        # QtCore.QObject.connect(self.animTimer, QtCore.SIGNAL('timeout()'), self.updateAnim)

        self.activateWindow()

        self.startAnim()

    def closeWindow(self):
        self.close()

    def showError(self, error):
        logger.error('got error: %s', error)
        self.stopAnim()
        self.ui.info.setText(
            'UDS Plugin Error'
        )  # In fact, main window is hidden, so this is not visible... :)
        self.closeWindow()
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'UDS Plugin Error',
            '{}'.format(error),
            QtWidgets.QMessageBox.Ok,
        )
        self.withError = True

    def cancelPushed(self):
        self.close()

    def updateAnim(self):
        self.anim += 2
        if self.anim > 99:
            self.animInverted = not self.animInverted
            self.ui.progressBar.setInvertedAppearance(self.animInverted)
            self.anim = 0

        self.ui.progressBar.setValue(self.anim)

    def startAnim(self):
        self.ui.progressBar.invertedAppearance = False  # type: ignore
        self.anim = 0
        self.animInverted = False
        self.ui.progressBar.setInvertedAppearance(self.animInverted)
        self.animTimer.start(40)

    def stopAnim(self):
        self.ui.progressBar.invertedAppearance = False  # type: ignore
        self.animTimer.stop()

    def getVersion(self):
        try:
            self.api.getVersion()
        except InvalidVersion as e:
            QtWidgets.QMessageBox.critical(
                self,
                'Upgrade required',
                'A newer connector version is required.\nA browser will be opened to download it.',
                QtWidgets.QMessageBox.Ok,
            )
            webbrowser.open(e.downloadUrl)
            self.closeWindow()
            return
        except Exception as e:
            self.showError(e)

        self.getTransportData()

    def getTransportData(self):
        try:
            script, params = self.api.getScriptAndParams(self.ticket, self.scrambler)
            self.stopAnim()

            if 'darwin' in sys.platform:
                self.showMinimized()

            # QtCore.QTimer.singleShot(3000, self.endScript)
            # self.hide()
            self.closeWindow()

            exec(script, globals(), {'parent': self, 'sp': params})

            # Execute the waiting tasks...
            threading.Thread(target=endScript).start()

        except RetryException as e:
            self.ui.info.setText(str(e) + ', retrying access...')
            # Retry operation in ten seconds
            QtCore.QTimer.singleShot(10000, self.getTransportData)
        except Exception as e:
            # logger.exception('Got exception on getTransportData')
            self.showError(e)

    def start(self):
        """
        Starts proccess by requesting version info
        """
        self.ui.info.setText('Initializing...')
        QtCore.QTimer.singleShot(100, self.getVersion)


def endScript():
    # Wait a bit before start processing ending sequence
    time.sleep(3)
    # After running script, wait for stuff
    try:
        logger.debug('Wating for tasks to finish...')
        tools.waitForTasks()
    except Exception as e:
        logger.debug('Watiting for tasks to finish: %s', e)

    try:
        logger.debug('Unlinking files')
        tools.unlinkFiles()
    except Exception as e:
        logger.debug('Unlinking files: %s', e)


    # Removing
    try:
        logger.debug('Executing threads before exit')
        tools.execBeforeExit()
    except Exception as e:
        logger.debug('execBeforeExit: %s', e)

    logger.debug('endScript done')


# Ask user to approve endpoint
def approveHost(hostName: str):
    settings = QtCore.QSettings()
    settings.beginGroup('endpoints')

    # approved = settings.value(hostName, False).toBool()
    approved = bool(settings.value(hostName, False))

    errorString = '<p>The server <b>{}</b> must be approved:</p>'.format(hostName)
    errorString += (
        '<p>Only approve UDS servers that you trust to avoid security issues.</p>'
    )

    if not approved:
        if (
            QtWidgets.QMessageBox.warning(
                None,  # type: ignore
                'ACCESS Warning',
                errorString,
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,  # type: ignore
            )
            == QtWidgets.QMessageBox.Yes
        ):
            settings.setValue(hostName, True)
            approved = True

    settings.endGroup()
    return approved


def sslError(hostname: str, serial):
    settings = QSettings()
    settings.beginGroup('ssl')

    approved = settings.value(serial, False)

    if (
        approved
        or QtWidgets.QMessageBox.warning(
            None,  # type: ignore
            'SSL Warning',
            f'Could not check sll certificate for {hostname}',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,  # type: ignore
        )
        == QtWidgets.QMessageBox.Yes
    ):
        approved = True
        settings.setValue(serial, True)

    settings.endGroup()
    return approved


# Used only if command line says so
def minimal(api: RestApi, ticket: str, scrambler: str):
    try:
        logger.info('M1 Execution')
        logger.debug('Getting version')
        try:
            api.getVersion()
        except InvalidVersion as e:
            QtWidgets.QMessageBox.critical(
                None,  # type: ignore
                'Upgrade required',
                'A newer connector version is required.\nA browser will be opened to download it.',
                QtWidgets.QMessageBox.Ok,
            )
            webbrowser.open(e.downloadUrl)
            return 0
        logger.debug('Transport data')
        script, params = api.getScriptAndParams(ticket, scrambler)

        # Execute UDS transport script
        exec(script, globals(), {'parent': None, 'sp': params})
        # Execute the waiting task...
        threading.Thread(target=endScript).start()

    except RetryException as e:
        QtWidgets.QMessageBox.warning(
            None,  # type: ignore
            'Service not ready',
            '{}'.format('.\n'.join(str(e).split('.')))
            + '\n\nPlease, retry again in a while.',
            QtWidgets.QMessageBox.Ok,
        )
    except Exception as e:
        # logger.exception('Got exception on getTransportData')
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'Error',
            '{}'.format(str(e)) + '\n\nPlease, retry again in a while.',
            QtWidgets.QMessageBox.Ok,
        )
    return 0


if __name__ == "__main__":
    logger.debug('Initializing connector for %s(%s)', sys.platform, platform.machine())

    # Initialize app
    app = QtWidgets.QApplication(sys.argv)

    # Set several info for settings
    QtCore.QCoreApplication.setOrganizationName('Virtual Cable S.L.U.')
    QtCore.QCoreApplication.setApplicationName('UDS Connector')

    if 'darwin' not in sys.platform:
        logger.debug('Mac OS *NOT* Detected')
        app.setStyle('plastique')  # type: ignore
    else:
        logger.debug('Platform is Mac OS, adding homebrew possible paths')
        os.environ['PATH'] += ''.join(os.pathsep + i for i in ('/usr/local/bin', '/opt/homebrew/bin',))
        logger.debug('Now path is %s', os.environ['PATH'])

    # First parameter must be url
    useMinimal = False
    try:
        uri = sys.argv[1]

        if uri == '--minimal':
            useMinimal = True
            uri = sys.argv[2]  # And get URI

        if uri == '--test':
            sys.exit(0)

        logger.debug('URI: %s', uri)
        if uri[:6] != 'uds://' and uri[:7] != 'udss://':
            raise Exception()

        ssl = uri[3] == 's'
        host, ticket, scrambler = uri.split('//')[1].split('/')  # type: ignore
        logger.debug(
            'ssl:%s, host:%s, ticket:%s, scrambler:%s',
            ssl,
            host,
            UDSClient.ticket,
            UDSClient.scrambler,
        )
    except Exception:
        logger.debug('Detected execution without valid URI, exiting')
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'Notice',
            'UDS Client Version {}'.format(VERSION),
            QtWidgets.QMessageBox.Ok,
        )
        sys.exit(1)

    # Setup REST api endpoint
    api = RestApi(
        '{}://{}/uds/rest/client'.format(['http', 'https'][ssl], host), sslError
    )

    try:
        logger.debug('Starting execution')

        # Approbe before going on
        if approveHost(host) is False:
            raise Exception('Host {} was not approved'.format(host))

        win = UDSClient(api, ticket, scrambler)
        win.show()

        win.start()

        exitVal = app.exec_()
        logger.debug('Execution finished correctly')

    except Exception as e:
        logger.exception('Got an exception executing client:')
        exitVal = 128
        QtWidgets.QMessageBox.critical(
            None, 'Error', str(e), QtWidgets.QMessageBox.Ok  # type: ignore
        )

    logger.debug('Exiting')
    sys.exit(exitVal)
