# -*- coding: utf-8 -*-

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
            self.ui.useSSl.setCurrentIndex(0 if data['ssl'] is True else 1)

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
        data = { 'host': self.ui.host.text(), 'masterKey': self.ui.masterKey.text(), 'ssl': self.ui.useSSl.currentIndex() == 0 }
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
