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
import sys
import os
import logging

import PyQt5  # pylint: disable=unused-import
from PyQt5.QtWidgets import QApplication, QDialog

from ui.setup_dialog_ui import Ui_UdsActorSetupDialog

# pylint: disable=invalid-name

logger = logging.getLogger('actor')


class UDSConfigDialog(QDialog):

    def __init__(self, data=None, parent=None):
        QDialog.__init__(self, parent)
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)
        if data is not None:
            pass

    def _getCfg(self):
        return {
            'host': self.ui.host.text(),
            'username': self.ui.username.text(),
            'password': self.ui.password.text(),
            'validateCertificate': self.ui.validateCertificate.currentIndex() == 1,
            'logLevel': (self.ui.logLevelComboBox.currentIndex() + 1) * 10000
        }

    def textChanged(self):
        enableButtons = self.ui.host.text() != '' and self.ui.username.text() != '' and self.ui.password.text() != ''
        self.ui.testButton.setEnabled(enableButtons)
        self.ui.saveButton.setEnabled(enableButtons)

    def cancelAndDiscard(self):
        logger.debug('Cancelling changes')
        self.close()

    def testParameters(self):
        pass

    def acceptAndSave(self):
        pass


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
