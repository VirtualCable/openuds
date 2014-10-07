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

from store import checkPermissions
from store import readConfig
from store import writeConfig

from setup_dialog_ui import Ui_UdsActorSetupDialog

class MyForm(QtGui.QDialog):
    def __init__(self, data, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)
        if data is not None:
            self.ui.host.setText(data['host'])
            self.ui.masterKey.setText(data['masterKey'])
            self.ui.useSSl.setCurrentIndex(1 if data['ssl'] is True else 0)

    def textChanged(self):
        enableButtons = self.ui.host.text() != '' and self.ui.masterKey.text() != ''
        self.ui.testButton.setEnabled(enableButtons)
        self.ui.saveButton.setEnabled(enableButtons)

    def cancelAndDiscard(self):
        # TODO: Check changes & show warning message box
        self.close()

    def testParameters(self):
        pass

    def acceptAndSave(self):
        data = { 'host': unicode(self.ui.host.text()), 'masterKey': unicode(self.ui.masterKey.text()), 'ssl': self.ui.useSSl.currentIndex() == 1 }
        writeConfig(data)
        self.close()

if __name__ == "__main__":

    app = QtGui.QApplication(sys.argv)

    if checkPermissions() == False:
        QtGui.QMessageBox.question(None, 'Notice', 'This Program must be executed as administrator', QtGui.QMessageBox.Ok)
        sys.exit(1)

    # Read configuration
    data = readConfig()

    myapp = MyForm(data)
    myapp.show()
    sys.exit(app.exec_())
