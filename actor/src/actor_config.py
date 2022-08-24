#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020-2022 Virtual Cable S.L.U.
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
import logging
import typing

import PyQt5  # Ensures PyQt is included in the package
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

import udsactor

from ui.setup_dialog_ui import Ui_UdsActorSetupDialog

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from PyQt5.QtWidgets import QLineEdit  # pylint: disable=ungrouped-imports

logger = logging.getLogger('actor')

class UDSConfigDialog(QDialog):
    _host: str = ''

    def __init__(self) -> None:
        QDialog.__init__(self, None)
        # Get local config config
        config: udsactor.types.ActorConfigurationType = udsactor.platform.store.readConfig()
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)
        self.ui.host.setText(config.host)
        self.ui.validateCertificate.setCurrentIndex(1 if config.validateCertificate else 0)
        self.ui.postConfigCommand.setText(config.post_command or '')
        self.ui.preCommand.setText(config.pre_command or '')
        self.ui.runonceCommand.setText(config.runonce_command or '')
        self.ui.logLevelComboBox.setCurrentIndex(config.log_level)

        if config.host:
            self.updateAuthenticators()

        self.ui.username.setText('')
        self.ui.password.setText('')

        self.ui.testButton.setEnabled(bool(config.master_token and config.host))

    @property
    def api(self) -> udsactor.rest.UDSServerApi:
        return udsactor.rest.UDSServerApi(self.ui.host.text(), self.ui.validateCertificate.currentIndex() == 1)

    def browse(self, lineEdit: 'QLineEdit', caption: str) -> None:
        name = QFileDialog.getOpenFileName(parent=self, caption=caption, directory=os.path.dirname(lineEdit.text()))[0]
        if name:
            if ' ' in name:
                name = '"' + name + '"'
            lineEdit.setText(os.path.normpath(name))

    def browsePreconnect(self) -> None:
        self.browse(self.ui.preCommand, 'Select Preconnect command')

    def browseRunOnce(self) -> None:
        self.browse(self.ui.runonceCommand, 'Select Runonce command')

    def browsePostConfig(self) -> None:
        self.browse(self.ui.postConfigCommand, 'Select Postconfig command')

    def updateAuthenticators(self) -> None:
        if self.ui.host.text() != self._host:
            self._host = self.ui.host.text()
            self.ui.authenticators.clear()
            auth: udsactor.types.AuthenticatorType
            auths = list(self.api.enumerateAuthenticators())
            if auths:
                for auth in auths:
                    self.ui.authenticators.addItem(auth.auth, userData=auth)
            # Last, add "admin" authenticator (for uds root user)
            self.ui.authenticators.addItem('Administration', userData=udsactor.types.AuthenticatorType('admin', 'admin', 'admin', 'admin', 1, False))

    def textChanged(self) -> None:
        enableButtons = bool(self.ui.host.text() and self.ui.username.text() and self.ui.password.text() and self.ui.authenticators.currentText())
        self.ui.registerButton.setEnabled(enableButtons)
        self.ui.testButton.setEnabled(False)  # Only registered information can be checked

    def finish(self) -> None:
        self.close()

    def testUDSServer(self) -> None:
        config: udsactor.types.ActorConfigurationType = udsactor.platform.store.readConfig()
        if not config.master_token or not config.host:
            self.ui.testButton.setEnabled(False)
            return
        try:
            api = udsactor.rest.UDSServerApi(config.host, config.validateCertificate)
            if not api.test(config.master_token, udsactor.types.MANAGED):
                QMessageBox.information(
                    self,
                    'UDS Test',
                    'Current configured token seems to be invalid for {}. Please, request a new one.'.format(config.host),
                    QMessageBox.Ok
                )
            else:
                QMessageBox.information(
                    self,
                    'UDS Test',
                    'Configuration for {} seems to be correct.'.format(config.host),
                    QMessageBox.Ok
                )
        except Exception:
            QMessageBox.information(
                self,
                'UDS Test',
                'Configured host {} seems to be inaccesible.'.format(config.host),
                QMessageBox.Ok
            )

    def registerWithUDS(self) -> None:
        # Get network card. Will fail if no network card is available, but don't mind (not contempled)
        data: udsactor.types.InterfaceInfoType = next(udsactor.platform.operations.getNetworkInfo())
        try:
            token = self.api.register(
                self.ui.authenticators.currentData().auth,
                self.ui.username.text(),
                self.ui.password.text(),
                udsactor.platform.operations.getComputerName(),
                data.ip or '',           # IP
                data.mac or '',          # MAC
                self.ui.preCommand.text(),
                self.ui.runonceCommand.text(),
                self.ui.postConfigCommand.text(),
                self.ui.logLevelComboBox.currentIndex()  # Loglevel
            )
            # Store parameters on register for later use, notify user of registration
            udsactor.platform.store.writeConfig(
                udsactor.types.ActorConfigurationType(
                    actorType=udsactor.types.MANAGED,
                    host=self.ui.host.text(),
                    validateCertificate=self.ui.validateCertificate.currentIndex() == 1,
                    master_token=token,
                    pre_command=self.ui.preCommand.text(),
                    post_command=self.ui.postConfigCommand.text(),
                    runonce_command=self.ui.runonceCommand.text(),
                    log_level=self.ui.logLevelComboBox.currentIndex()
                )
            )
            # Enables test button
            self.ui.testButton.setEnabled(True)
            # Informs the user
            QMessageBox.information(self, 'UDS Registration', 'Registration with UDS completed.', QMessageBox.Ok)
        except udsactor.rest.RESTError as e:
            self.ui.testButton.setEnabled(False)
            QMessageBox.critical(self, 'UDS Registration', 'UDS Registration error: {}'.format(e), QMessageBox.Ok)


if __name__ == "__main__":
    # If to be run as "sudo" on linux, we will need this to avoid problems
    if 'linux' in sys.platform:
        os.environ['QT_X11_NO_MITSHM'] = '1'

    app = QApplication(sys.argv)

    if udsactor.platform.operations.checkPermissions() is False:
        QMessageBox.critical(None, 'UDS Actor', 'This Program must be executed as administrator', QMessageBox.Ok)  # type: ignore
        sys.exit(1)

    myapp = UDSConfigDialog()
    myapp.show()
    sys.exit(app.exec())
