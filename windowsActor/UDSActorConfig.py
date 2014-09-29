# -*- coding: utf-8 -*-

import sys
from PyQt4 import QtCore, QtGui

from store import checkPermissions

from setup_dialog_ui import Ui_UdsActorSetupDialog

class MyForm(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)

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
        pass

if __name__ == "__main__":

    app = QtGui.QApplication(sys.argv)

    if checkPermissions() == True:
        QtGui.QMessageBox.question(None, 'Notice', 'This Program must be executed as administrator', QtGui.QMessageBox.Ok)
        sys.exit(1)

    myapp = MyForm()
    myapp.show()
    sys.exit(app.exec_())
