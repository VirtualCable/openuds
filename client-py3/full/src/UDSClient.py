#!/usr/bin/env -S python3 -s
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

from uds.ui import QtCore, QtWidgets, QtGui, QSettings, Ui_MainWindow  # type: ignore
from uds.rest import RestApi, RetryException, InvalidVersion

# Just to ensure there are available on runtime
from uds.forward import forward as ssh_forward  # type: ignore  # pylint: disable=unused-import
from uds.tunnel import forward as tunnel_forwards  # type: ignore  # pylint: disable=unused-import

from uds.log import logger
from uds import tools
from uds import VERSION


class UDSClient(QtWidgets.QMainWindow):  # type: ignore
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
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.progressBar.setValue(0)
        self.ui.cancelButton.clicked.connect(self.cancelPushed)

        self.ui.info.setText('Initializing...')

        screen_geometry = QtGui.QGuiApplication.primaryScreen().geometry()
        mysize = self.geometry()
        hpos = (screen_geometry.width() - mysize.width()) // 2
        vpos = (screen_geometry.height() - mysize.height() - mysize.height()) // 2
        self.move(hpos, vpos)

        self.animTimer = QtCore.QTimer()
        self.animTimer.timeout.connect(self.updateAnim)
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
            QtWidgets.QMessageBox.StandardButton.Ok,
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
        self.ui.progressBar.setInvertedAppearance(False)
        self.anim = 0
        self.animInverted = False
        self.ui.progressBar.setInvertedAppearance(self.animInverted)
        if self.animTimer:
            self.animTimer.start(40)

    def stopAnim(self):
        self.ui.progressBar.setInvertedAppearance(False)
        if self.animTimer:
            self.animTimer.stop()

    def getVersion(self):
        try:
            self.api.getVersion()
        except InvalidVersion as e:
            QtWidgets.QMessageBox.critical(
                self,
                'Upgrade required',
                'A newer connector version is required.\nA browser will be opened to download it.',
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            webbrowser.open(e.downloadUrl)
            self.closeWindow()
            return
        except Exception as e:  # pylint: disable=broad-exception-caught
            if logger.getEffectiveLevel() == 10:
                logger.exception('Get Version')
            self.showError(e)
            self.closeWindow()
            return

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

            exec(
                script, globals(), {'parent': self, 'sp': params}
            )  # pylint: disable=exec-used

            # Execute the waiting tasks...
            threading.Thread(target=endScript).start()

        except RetryException as e:
            self.ui.info.setText(str(e) + ', retrying access...')
            # Retry operation in ten seconds
            QtCore.QTimer.singleShot(10000, self.getTransportData)
        except Exception as e:  # pylint: disable=broad-exception-caught
            if logger.getEffectiveLevel() == 10:
                logger.exception('Get Transport Data')
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
    try:
        # Remove early stage files...
        tools.unlinkFiles(early=True)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug('Unlinking files on early stage: %s', e)

    # After running script, wait for stuff
    try:
        logger.debug('Wating for tasks to finish...')
        tools.waitForTasks()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug('Watiting for tasks to finish: %s', e)

    try:
        logger.debug('Unlinking files')
        tools.unlinkFiles(early=False)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.debug('Unlinking files on later stage: %s', e)

    # Removing
    try:
        logger.debug('Executing threads before exit')
        tools.execBeforeExit()
    except Exception as e:  # pylint: disable=broad-exception-caught
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
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            )
            == QtWidgets.QMessageBox.StandardButton.Yes
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
            f'Could not check SSL certificate for {hostname}.\nDo you trust this host?',
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        == QtWidgets.QMessageBox.StandardButton.Yes
    ):
        approved = True
        settings.setValue(serial, True)

    settings.endGroup()
    return approved


# Used only if command line says so
def minimal(api: RestApi, ticket: str, scrambler: str):
    try:
        logger.info('Minimal Execution')
        logger.debug('Getting version')
        try:
            api.getVersion()
        except InvalidVersion as e:
            QtWidgets.QMessageBox.critical(
                None,  # type: ignore
                'Upgrade required',
                'A newer connector version is required.\nA browser will be opened to download it.',
                QtWidgets.QMessageBox.StandardButton.Ok,
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
            QtWidgets.QMessageBox.StandardButton.Ok,
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        # logger.exception('Got exception on getTransportData')
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'Error',
            '{}'.format(str(e)) + '\n\nPlease, retry again in a while.',
            QtWidgets.QMessageBox.StandardButton.Ok,
        )
    return 0


def main(args: typing.List[str]):
    app = QtWidgets.QApplication(sys.argv)
    logger.debug('Initializing connector for %s(%s)', sys.platform, platform.machine())

    logger.debug('Arguments: %s', args)
    # Set several info for settings
    QtCore.QCoreApplication.setOrganizationName('Virtual Cable S.L.U.')
    QtCore.QCoreApplication.setApplicationName('UDS Connector')

    if 'darwin' not in sys.platform:
        logger.debug('Mac OS *NOT* Detected')
        app.setStyle('plastique')
    else:
        logger.debug('Platform is Mac OS, adding homebrew possible paths')
        os.environ['PATH'] += ''.join(
            os.pathsep + i
            for i in (
                '/usr/local/bin',
                '/opt/homebrew/bin',
            )
        )
        logger.debug('Now path is %s', os.environ['PATH'])

    # First parameter must be url
    useMinimal = False
    try:
        uri = args[1]

        if uri == '--minimal':
            useMinimal = True
            uri = args[2]  # And get URI

        if uri == '--test':
            sys.exit(0)

        logger.debug('URI: %s', uri)
        # Shows error if using http (uds:// ) version, not supported anymore
        if uri[:6] == 'uds://':
            QtWidgets.QMessageBox.critical(
                None,  # type: ignore
                'Notice',
                f'UDS Client Version {VERSION} does not support HTTP protocol Anymore.',
                QtWidgets.QMessageBox.StandardButton.Ok,
            )
            sys.exit(1)
        if uri[:7] != 'udss://':
            raise Exception('Not supported protocol')  # Just shows "about" dialog

        host, ticket, scrambler = uri.split('//')[1].split('/')  # type: ignore
        logger.debug(
            'host:%s, ticket:%s, scrambler:%s',
            host,
            ticket,
            scrambler,
        )
    except Exception:  # pylint: disable=broad-except
        logger.debug('Detected execution without valid URI, exiting')
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'Notice',
            f'UDS Client Version {VERSION}',
            QtWidgets.QMessageBox.StandardButton.Ok,
        )
        sys.exit(1)

    # Setup REST api endpoint
    api = RestApi(
        f'https://{host}/uds/rest/client', sslError
    )

    try:
        logger.debug('Starting execution')

        # Approbe before going on
        if approveHost(host) is False:
            raise Exception('Host {} was not approved'.format(host))

        win = UDSClient(api, ticket, scrambler)
        win.show()

        win.start()

        exitVal = app.exec()
        logger.debug('Execution finished correctly')

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.exception('Got an exception executing client:')
        exitVal = 128
        QtWidgets.QMessageBox.critical(
            None,  # type: ignore
            'Error', 
            f'Fatal error: {e}',
            QtWidgets.QMessageBox.StandardButton.Ok
        )

    logger.debug('Exiting')
    sys.exit(exitVal)


if __name__ == "__main__":
    main(sys.argv)
