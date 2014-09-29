# -*- coding: utf-8 -*-

import sys
from PyQt4 import QtCore, QtGui

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

if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    myapp = MyForm()
    myapp.show()
    sys.exit(app.exec_())
