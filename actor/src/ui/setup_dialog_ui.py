# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'setup-dialog.ui'
#
# Created by: PyQt5 UI code generator 5.11.3
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_UdsActorSetupDialog(object):
    def setupUi(self, UdsActorSetupDialog):
        UdsActorSetupDialog.setObjectName("UdsActorSetupDialog")
        UdsActorSetupDialog.setWindowModality(QtCore.Qt.WindowModal)
        UdsActorSetupDialog.resize(400, 293)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(UdsActorSetupDialog.sizePolicy().hasHeightForWidth())
        UdsActorSetupDialog.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Verdana")
        font.setPointSize(9)
        UdsActorSetupDialog.setFont(font)
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(":/img/img/uds-icon.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        UdsActorSetupDialog.setWindowIcon(icon)
        UdsActorSetupDialog.setAutoFillBackground(False)
        UdsActorSetupDialog.setLocale(QtCore.QLocale(QtCore.QLocale.English, QtCore.QLocale.UnitedStates))
        UdsActorSetupDialog.setSizeGripEnabled(False)
        UdsActorSetupDialog.setModal(True)
        self.testButton = QtWidgets.QPushButton(UdsActorSetupDialog)
        self.testButton.setEnabled(False)
        self.testButton.setGeometry(QtCore.QRect(20, 220, 361, 23))
        self.testButton.setObjectName("testButton")
        self.saveButton = QtWidgets.QPushButton(UdsActorSetupDialog)
        self.saveButton.setEnabled(False)
        self.saveButton.setGeometry(QtCore.QRect(20, 250, 101, 23))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.saveButton.sizePolicy().hasHeightForWidth())
        self.saveButton.setSizePolicy(sizePolicy)
        self.saveButton.setObjectName("saveButton")
        self.cancelButton = QtWidgets.QPushButton(UdsActorSetupDialog)
        self.cancelButton.setGeometry(QtCore.QRect(260, 250, 121, 23))
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.cancelButton.sizePolicy().hasHeightForWidth())
        self.cancelButton.setSizePolicy(sizePolicy)
        self.cancelButton.setObjectName("cancelButton")
        self.layoutWidget = QtWidgets.QWidget(UdsActorSetupDialog)
        self.layoutWidget.setGeometry(QtCore.QRect(20, 20, 361, 191))
        self.layoutWidget.setObjectName("layoutWidget")
        self.formLayout = QtWidgets.QFormLayout(self.layoutWidget)
        self.formLayout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        self.formLayout.setContentsMargins(0, 0, 0, 0)
        self.formLayout.setVerticalSpacing(16)
        self.formLayout.setObjectName("formLayout")
        self.label_host = QtWidgets.QLabel(self.layoutWidget)
        self.label_host.setObjectName("label_host")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_host)
        self.host = QtWidgets.QLineEdit(self.layoutWidget)
        self.host.setAcceptDrops(False)
        self.host.setObjectName("host")
        self.formLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.host)
        self.label_username = QtWidgets.QLabel(self.layoutWidget)
        self.label_username.setObjectName("label_username")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.LabelRole, self.label_username)
        self.username = QtWidgets.QLineEdit(self.layoutWidget)
        self.username.setObjectName("username")
        self.formLayout.setWidget(1, QtWidgets.QFormLayout.FieldRole, self.username)
        self.password = QtWidgets.QLineEdit(self.layoutWidget)
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password.setObjectName("password")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.password)
        self.label_password = QtWidgets.QLabel(self.layoutWidget)
        self.label_password.setObjectName("label_password")
        self.formLayout.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_password)
        self.label_security = QtWidgets.QLabel(self.layoutWidget)
        self.label_security.setObjectName("label_security")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.LabelRole, self.label_security)
        self.validateCertificate = QtWidgets.QComboBox(self.layoutWidget)
        self.validateCertificate.setObjectName("validateCertificate")
        self.validateCertificate.addItem("")
        self.validateCertificate.addItem("")
        self.formLayout.setWidget(3, QtWidgets.QFormLayout.FieldRole, self.validateCertificate)
        self.logLevelComboBox = QtWidgets.QComboBox(self.layoutWidget)
        self.logLevelComboBox.setFrame(True)
        self.logLevelComboBox.setObjectName("logLevelComboBox")
        self.logLevelComboBox.addItem("")
        self.logLevelComboBox.setItemText(0, "DEBUG")
        self.logLevelComboBox.addItem("")
        self.logLevelComboBox.setItemText(1, "INFO")
        self.logLevelComboBox.addItem("")
        self.logLevelComboBox.setItemText(2, "ERROR")
        self.logLevelComboBox.addItem("")
        self.logLevelComboBox.setItemText(3, "FATAL")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.FieldRole, self.logLevelComboBox)
        self.label_loglevel = QtWidgets.QLabel(self.layoutWidget)
        self.label_loglevel.setObjectName("label_loglevel")
        self.formLayout.setWidget(4, QtWidgets.QFormLayout.LabelRole, self.label_loglevel)

        self.retranslateUi(UdsActorSetupDialog)
        self.logLevelComboBox.setCurrentIndex(1)
        self.cancelButton.pressed.connect(UdsActorSetupDialog.cancelAndDiscard)
        self.testButton.pressed.connect(UdsActorSetupDialog.testParameters)
        self.saveButton.pressed.connect(UdsActorSetupDialog.acceptAndSave)
        self.host.textChanged['QString'].connect(UdsActorSetupDialog.textChanged)
        self.username.textChanged['QString'].connect(UdsActorSetupDialog.textChanged)
        self.password.textChanged['QString'].connect(UdsActorSetupDialog.textChanged)
        QtCore.QMetaObject.connectSlotsByName(UdsActorSetupDialog)

    def retranslateUi(self, UdsActorSetupDialog):
        _translate = QtCore.QCoreApplication.translate
        UdsActorSetupDialog.setWindowTitle(_translate("UdsActorSetupDialog", "UDS Actor Setup"))
        self.testButton.setToolTip(_translate("UdsActorSetupDialog", "Click to test the selecter parameters"))
        self.testButton.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Click on this button to test the server host and master key parameters.</p><p>A window will be displayed with results after the test is executed.</p><p><br/></p><p>This button will only be active if all parameters are filled.</p></body></html>"))
        self.testButton.setText(_translate("UdsActorSetupDialog", "Test parameters"))
        self.saveButton.setToolTip(_translate("UdsActorSetupDialog", "Accepts changes and saves them"))
        self.saveButton.setWhatsThis(_translate("UdsActorSetupDialog", "Clicking on this button will accept all changes and save them, closing the configuration window"))
        self.saveButton.setText(_translate("UdsActorSetupDialog", "Accept && Save"))
        self.cancelButton.setToolTip(_translate("UdsActorSetupDialog", "Cancel all changes and discard them"))
        self.cancelButton.setWhatsThis(_translate("UdsActorSetupDialog", "Discards all changes and closes the configuration window"))
        self.cancelButton.setText(_translate("UdsActorSetupDialog", "Cancel && Discard"))
        self.label_host.setText(_translate("UdsActorSetupDialog", "UDS Server"))
        self.host.setToolTip(_translate("UdsActorSetupDialog", "Uds Broker Server Addres. Use IP or FQDN"))
        self.host.setWhatsThis(_translate("UdsActorSetupDialog", "Enter here the UDS Broker Addres using either its IP address or its FQDN address"))
        self.label_username.setText(_translate("UdsActorSetupDialog", "Username"))
        self.username.setToolTip(_translate("UdsActorSetupDialog", "UDS user with administration rights (Will not be stored on template)"))
        self.username.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Administrator user on UDS Server.</p><p>Note: This credential will not be stored on client. Will be used to obtain an unique key for this image.</p></body></html>"))
        self.password.setToolTip(_translate("UdsActorSetupDialog", "Password for user (Will not be stored on template)"))
        self.password.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Administrator password for the user on UDS Server.</p><p>Note: This credential will not be stored on client. Will be used to obtain an unique key for this image.</p></body></html>"))
        self.label_password.setText(_translate("UdsActorSetupDialog", "Password"))
        self.label_security.setText(_translate("UdsActorSetupDialog", "Security"))
        self.validateCertificate.setToolTip(_translate("UdsActorSetupDialog", "Select communication security with broker"))
        self.validateCertificate.setWhatsThis(_translate("UdsActorSetupDialog", "<html><head/><body><p>Select the security for communications with UDS Broker.</p><p>The recommended method of communication is <span style=\" font-weight:600;\">Use SSL</span>, but selection needs to be acording to your broker configuration.</p></body></html>"))
        self.validateCertificate.setItemText(0, _translate("UdsActorSetupDialog", "Ignore certificate"))
        self.validateCertificate.setItemText(1, _translate("UdsActorSetupDialog", "Verify certificate"))
        self.label_loglevel.setText(_translate("UdsActorSetupDialog", "Log Level"))

from ui import uds_rc
