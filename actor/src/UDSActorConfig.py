#!/usr/bin/env python3
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
import sys
import os
import logging
import typing

import PyQt5  # pylint: disable=unused-import
from PyQt5.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

import udsactor

from ui.setup_dialog_ui import Ui_UdsActorSetupDialog

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from PyQt5.QtWidgets import QLineEdit  # pylint: disable=ungrouped-imports

logger = logging.getLogger('actor')


class UDSConfigDialog(QDialog):
    _host: str = ''

    def __init__(self):
        QDialog.__init__(self, None)
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)
        self.ui.host.setText('172.27.0.1:8443')
        self.ui.username.setText('admin')
        self.ui.password.setText('temporal')
        self.ui.postConfigCommand.setText(r'c:\windows\post-uds.bat')
        self.ui.preCommand.setText(r'c:\windows\pre-uds.bat')
        self.ui.runonceCommand.setText(r'c:\windows\runonce.bat')

    @property
    def api(self) -> udsactor.rest.REST:
        return udsactor.rest.REST(self.ui.host.text(), self.ui.validateCertificate.currentIndex() == 1)

    def browse(self, lineEdit: 'QLineEdit', caption: str) -> None:
        name = QFileDialog.getOpenFileName(parent=self, caption='')[0]  # Returns tuple (filename, filter)
        if name:
            lineEdit.setText(name)

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
            for auth in self.api.enumerateAuthenticators():
                self.ui.authenticators.addItem(auth.auth, userData=auth)

    def textChanged(self):
        enableButtons = self.ui.host.text() != '' and self.ui.username.text() != '' and self.ui.password.text() != ''
        self.ui.registerButton.setEnabled(enableButtons)

    def finish(self):
        self.close()

    def registerWithUDS(self):
        # Get network card. Will fail if no network card is available, but don't mind (not contempled)
        data: udsactor.types.InterfaceInfo = next(udsactor.operations.getNetworkInfo())

        key = self.api.register(
            self.ui.authenticators.currentData().auth,
            self.ui.username.text(),
            self.ui.password.text(),
            data.ip or '',           # IP
            data.mac or '',          # MAC
            self.ui.preCommand.text(),
            self.ui.runonceCommand.text(),
            self.ui.postConfigCommand.text()
        )

        print(key)


if __name__ == "__main__":
    # If to be run as "sudo" on linux, we will need this to avoid problems
    if 'linux' in sys.platform:
        os.environ['QT_X11_NO_MITSHM'] = '1'

    app = QApplication(sys.argv)

    # if store.checkPermissions() is False:
    #    QtGui.QMessageBox.critical(None, 'Notice', 'This Program must be executed as administrator', QtGui.QMessageBox.Ok)
    #    sys.exit(1)

    myapp = UDSConfigDialog()
    myapp.show()
    sys.exit(app.exec_())
