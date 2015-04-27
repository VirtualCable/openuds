# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'message-dialog.ui'
#
# Created: Mon Apr 27 22:05:02 2015
#      by: PyQt4 UI code generator 4.11.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_UDSMessageDialog(object):
    def setupUi(self, UDSMessageDialog):
        UDSMessageDialog.setObjectName(_fromUtf8("UDSMessageDialog"))
        UDSMessageDialog.resize(339, 188)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(UDSMessageDialog.sizePolicy().hasHeightForWidth())
        UDSMessageDialog.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Verdana"))
        font.setPointSize(10)
        UDSMessageDialog.setFont(font)
        self.verticalLayoutWidget = QtGui.QWidget(UDSMessageDialog)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(10, 10, 321, 171))
        self.verticalLayoutWidget.setObjectName(_fromUtf8("verticalLayoutWidget"))
        self.verticalLayout = QtGui.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setMargin(0)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.message = QtGui.QTextBrowser(self.verticalLayoutWidget)
        self.message.setObjectName(_fromUtf8("message"))
        self.verticalLayout.addWidget(self.message)
        spacerItem = QtGui.QSpacerItem(20, 15, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Fixed)
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtGui.QDialogButtonBox(self.verticalLayoutWidget)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Ok)
        self.buttonBox.setObjectName(_fromUtf8("buttonBox"))
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(UDSMessageDialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL(_fromUtf8("clicked(QAbstractButton*)")), UDSMessageDialog.closeDialog)
        QtCore.QMetaObject.connectSlotsByName(UDSMessageDialog)

    def retranslateUi(self, UDSMessageDialog):
        UDSMessageDialog.setWindowTitle(_translate("UDSMessageDialog", "UDS Actor", None))


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    UDSMessageDialog = QtGui.QDialog()
    ui = Ui_UDSMessageDialog()
    ui.setupUi(UDSMessageDialog)
    UDSMessageDialog.show()
    sys.exit(app.exec_())

