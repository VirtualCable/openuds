# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'setup-dialog.ui'
#
# Created: Mon Apr 27 22:05:03 2015
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

class Ui_UdsActorSetupDialog(object):
    def setupUi(self, UdsActorSetupDialog):
        UdsActorSetupDialog.setObjectName(_fromUtf8("UdsActorSetupDialog"))
        UdsActorSetupDialog.setWindowModality(QtCore.Qt.WindowModal)
        UdsActorSetupDialog.resize(400, 243)
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(UdsActorSetupDialog.sizePolicy().hasHeightForWidth())
        UdsActorSetupDialog.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily(_fromUtf8("Verdana"))
        font.setPointSize(9)
        UdsActorSetupDialog.setFont(font)
        UdsActorSetupDialog.setAutoFillBackground(False)
        UdsActorSetupDialog.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        UdsActorSetupDialog.setSizeGripEnabled(False)
        UdsActorSetupDialog.setModal(True)
        self.testButton = QtGui.QPushButton(UdsActorSetupDialog)
        self.testButton.setEnabled(False)
        self.testButton.setGeometry(QtCore.QRect(20, 160, 361, 23))
        self.testButton.setObjectName(_fromUtf8("testButton"))
        self.saveButton = QtGui.QPushButton(UdsActorSetupDialog)
        self.saveButton.setEnabled(False)
        self.saveButton.setGeometry(QtCore.QRect(20, 190, 101, 23))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.saveButton.sizePolicy().hasHeightForWidth())
        self.saveButton.setSizePolicy(sizePolicy)
        self.saveButton.setObjectName(_fromUtf8("saveButton"))
        self.cancelButton = QtGui.QPushButton(UdsActorSetupDialog)
        self.cancelButton.setGeometry(QtCore.QRect(260, 190, 121, 23))
        sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cancelButton.sizePolicy().hasHeightForWidth())
        self.cancelButton.setSizePolicy(sizePolicy)
        self.cancelButton.setObjectName(_fromUtf8("cancelButton"))
        self.layoutWidget = QtGui.QWidget(UdsActorSetupDialog)
        self.layoutWidget.setGeometry(QtCore.QRect(20, 20, 361, 131))
        self.layoutWidget.setObjectName(_fromUtf8("layoutWidget"))
        self.formLayout = QtGui.QFormLayout(self.layoutWidget)
        self.formLayout.setFieldGrowthPolicy(QtGui.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout.setMargin(0)
        self.formLayout.setVerticalSpacing(16)
        self.formLayout.setObjectName(_fromUtf8("formLayout"))
        self.label = QtGui.QLabel(self.layoutWidget)
        self.label.setObjectName(_fromUtf8("label"))
        self.formLayout.setWidget(0, QtGui.QFormLayout.LabelRole, self.label)
        self.host = QtGui.QLineEdit(self.layoutWidget)
        self.host.setAcceptDrops(False)
        self.host.setObjectName(_fromUtf8("host"))
        self.formLayout.setWidget(0, QtGui.QFormLayout.FieldRole, self.host)
        self.label_3 = QtGui.QLabel(self.layoutWidget)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.formLayout.setWidget(1, QtGui.QFormLayout.LabelRole, self.label_3)
        self.masterKey = QtGui.QLineEdit(self.layoutWidget)
        self.masterKey.setObjectName(_fromUtf8("masterKey"))
        self.formLayout.setWidget(1, QtGui.QFormLayout.FieldRole, self.masterKey)
        self.label_4 = QtGui.QLabel(self.layoutWidget)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.formLayout.setWidget(2, QtGui.QFormLayout.LabelRole, self.label_4)
        self.useSSl = QtGui.QComboBox(self.layoutWidget)
        self.useSSl.setObjectName(_fromUtf8("useSSl"))
        self.useSSl.addItem(_fromUtf8(""))
        self.useSSl.addItem(_fromUtf8(""))
        self.formLayout.setWidget(2, QtGui.QFormLayout.FieldRole, self.useSSl)
        self.logLevelLabel = QtGui.QLabel(self.layoutWidget)
        self.logLevelLabel.setObjectName(_fromUtf8("logLevelLabel"))
        self.formLayout.setWidget(3, QtGui.QFormLayout.LabelRole, self.logLevelLabel)
        self.logLevelComboBox = QtGui.QComboBox(self.layoutWidget)
        self.logLevelComboBox.setFrame(True)
        self.logLevelComboBox.setObjectName(_fromUtf8("logLevelComboBox"))
        self.logLevelComboBox.addItem(_fromUtf8(""))
        self.logLevelComboBox.setItemText(0, _fromUtf8("DEBUG"))
        self.logLevelComboBox.addItem(_fromUtf8(""))
        self.logLevelComboBox.setItemText(1, _fromUtf8("INFO"))
        self.logLevelComboBox.addItem(_fromUtf8(""))
        self.logLevelComboBox.setItemText(2, _fromUtf8("ERROR"))
        self.logLevelComboBox.addItem(_fromUtf8(""))
        self.logLevelComboBox.setItemText(3, _fromUtf8("FATAL"))
        self.formLayout.setWidget(3, QtGui.QFormLayout.FieldRole, self.logLevelComboBox)

        self.retranslateUi(UdsActorSetupDialog)
        self.logLevelComboBox.setCurrentIndex(1)
        QtCore.QObject.connect(self.host, QtCore.SIGNAL(_fromUtf8("textChanged(QString)")), UdsActorSetupDialog.textChanged)
        QtCore.QObject.connect(self.masterKey, QtCore.SIGNAL(_fromUtf8("textChanged(QString)")), UdsActorSetupDialog.textChanged)
        QtCore.QObject.connect(self.cancelButton, QtCore.SIGNAL(_fromUtf8("pressed()")), UdsActorSetupDialog.cancelAndDiscard)
        QtCore.QObject.connect(self.testButton, QtCore.SIGNAL(_fromUtf8("pressed()")), UdsActorSetupDialog.testParameters)
        QtCore.QObject.connect(self.saveButton, QtCore.SIGNAL(_fromUtf8("pressed()")), UdsActorSetupDialog.acceptAndSave)
        QtCore.QMetaObject.connectSlotsByName(UdsActorSetupDialog)

    def retranslateUi(self, UdsActorSetupDialog):
        UdsActorSetupDialog.setWindowTitle(_translate("UdsActorSetupDialog", "UDS Actor Configuration", None))
        self.testButton.setToolTip(_translate("UdsActorSetupDialog", "Click to test the selecter parameters", None))
        self.testButton.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Click on this button to test the server host and master key parameters.</p><p>A window will be displayed with results after the test is executed.</p><p><br/></p><p>This button will only be active if all parameters are filled.</p></body></html>", None))
        self.testButton.setText(_translate("UdsActorSetupDialog", "Test parameters", None))
        self.saveButton.setToolTip(_translate("UdsActorSetupDialog", "Accepts changes and saves them", None))
        self.saveButton.setWhatsThis(_translate("UdsActorSetupDialog", "Clicking on this button will accept all changes and save them, closing the configuration window", None))
        self.saveButton.setText(_translate("UdsActorSetupDialog", "Accept && Save", None))
        self.cancelButton.setToolTip(_translate("UdsActorSetupDialog", "Cancel all changes and discard them", None))
        self.cancelButton.setWhatsThis(_translate("UdsActorSetupDialog", "Discards all changes and closes the configuration window", None))
        self.cancelButton.setText(_translate("UdsActorSetupDialog", "Cancel && Discard", None))
        self.label.setText(_translate("UdsActorSetupDialog", "UDS Server Host", None))
        self.host.setToolTip(_translate("UdsActorSetupDialog", "Uds Broker Server Addres. Use IP or FQDN", None))
        self.host.setWhatsThis(_translate("UdsActorSetupDialog", "Enter here the UDS Broker Addres using either its IP address or its FQDN address", None))
        self.label_3.setText(_translate("UdsActorSetupDialog", "UDS Master Key", None))
        self.masterKey.setToolTip(_translate("UdsActorSetupDialog", "Master key to communicate with UDS Broker", None))
        self.masterKey.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Enter the Master Key (found on<span style=\" font-weight:600;\"> UDS Configuration</span> section) of the UDS Broker to allow communication of the Actor with Broker</p></body></html>", None))
        self.label_4.setText(_translate("UdsActorSetupDialog", "Security", None))
        self.useSSl.setToolTip(_translate("UdsActorSetupDialog", "Select communication security with broker", None))
        self.useSSl.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Select the security for communications with UDS Broker.</p><p>The recommended method of communication is <span style=\" font-weight:600;\">Use SSL</span>, but selection needs to be acording to your broker configuration.</p></body></html>", None))
        self.useSSl.setItemText(0, _translate("UdsActorSetupDialog", "Do not use SSL", None))
        self.useSSl.setItemText(1, _translate("UdsActorSetupDialog", "Use SSL", None))
        self.logLevelLabel.setText(_translate("UdsActorSetupDialog", "Log Level", None))


if __name__ == "__main__":
    import sys
    app = QtGui.QApplication(sys.argv)
    UdsActorSetupDialog = QtGui.QDialog()
    ui = Ui_UdsActorSetupDialog()
    ui.setupUi(UdsActorSetupDialog)
    UdsActorSetupDialog.show()
    sys.exit(app.exec_())

