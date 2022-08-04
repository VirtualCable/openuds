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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
import pickle  # nosec: B403
import logging
import typing

import PyQt5  # pylint: disable=unused-import
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox

import udsactor
import udsactor.tools

from ui.setup_dialog_unmanaged_ui import Ui_UdsActorSetupDialog

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from PyQt5.QtWidgets import QLineEdit  # pylint: disable=ungrouped-imports

logger = logging.getLogger('actor')


class UDSConfigDialog(QDialog):
    _host: str = ''
    _config: udsactor.types.ActorConfigurationType

    def __init__(self) -> None:
        QDialog.__init__(self, None)
        # Get local config config
        self._config = udsactor.platform.store.readConfig()
        self.ui = Ui_UdsActorSetupDialog()
        self.ui.setupUi(self)
        self.ui.host.setText(self._config.host)
        self.ui.validateCertificate.setCurrentIndex(
            1 if self._config.validateCertificate else 0
        )
        self.ui.logLevelComboBox.setCurrentIndex(self._config.log_level)
        self.ui.serviceToken.setText(self._config.master_token or '')
        self.ui.restrictNet.setText(self._config.restrict_net or '')

        self.ui.testButton.setEnabled(
            bool(self._config.master_token and self._config.host)
        )

    @property
    def api(self) -> udsactor.rest.UDSServerApi:
        return udsactor.rest.UDSServerApi(
            self.ui.host.text(), self.ui.validateCertificate.currentIndex() == 1
        )

    def finish(self) -> None:
        self.close()

    def configChanged(self, text: str) -> None:
        self.ui.testButton.setEnabled(
            self.ui.host.text() == self._config.host
            and self.ui.serviceToken.text() == self._config.master_token
            and self.ui.restrictNet.text() == self._config.restrict_net
        )

    def testUDSServer(self) -> None:
        if not self._config.master_token or not self._config.host:
            self.ui.testButton.setEnabled(False)
            return
        try:
            api = udsactor.rest.UDSServerApi(
                self._config.host, self._config.validateCertificate
            )
            if not api.test(self._config.master_token, udsactor.types.UNMANAGED):
                QMessageBox.information(
                    self,
                    'UDS Test',
                    'Service token seems to be invalid . Please, check token validity.',
                    QMessageBox.Ok,  # type: ignore
                )
            else:
                QMessageBox.information(
                    self,
                    'UDS Test',
                    'Configuration for {} seems to be correct.'.format(
                        self._config.host
                    ),
                    QMessageBox.Ok,  # type: ignore
                )
        except Exception:
            QMessageBox.information(
                self,
                'UDS Test',
                'Configured host {} seems to be inaccesible.'.format(self._config.host),
                QMessageBox.Ok,  # type: ignore
            )

    def saveConfig(self) -> None:
        # Ensure restrict_net is empty or a valid subnet
        restrictNet = self.ui.restrictNet.text().strip()
        if restrictNet:
            try:
                subnet = udsactor.tools.strToNoIPV4Network(restrictNet)
                if not subnet:
                    raise Exception('Invalid subnet')
            except Exception:
                QMessageBox.information(
                    self,
                    'Invalid subnet',
                    'Invalid subnet {}. Please, check it.'.format(restrictNet),
                    QMessageBox.Ok,  # type: ignore
                )
                return

        # Store parameters on register for later use, notify user of registration
        self._config = udsactor.types.ActorConfigurationType(
            actorType=udsactor.types.UNMANAGED,
            host=self.ui.host.text(),
            validateCertificate=self.ui.validateCertificate.currentIndex() == 1,
            master_token=self.ui.serviceToken.text().strip(),
            restrict_net=restrictNet,
            log_level=self.ui.logLevelComboBox.currentIndex(),
        )

        udsactor.platform.store.writeConfig(self._config)
        # Enables test button
        self.ui.testButton.setEnabled(True)
        # Informs the user
        QMessageBox.information(
            self,
            'UDS Configuration',
            'Configuration saved.',
            QMessageBox.Ok,  # type: ignore
        )


if __name__ == "__main__":
    # If run as "sudo" on linux, we will need this to avoid problems
    if 'linux' in sys.platform:
        os.environ['QT_X11_NO_MITSHM'] = '1'

    app = QApplication(sys.argv)

    if udsactor.platform.operations.checkPermissions() is False:
        QMessageBox.critical(None, 'UDS Actor', 'This Program must be executed as administrator', QMessageBox.Ok)  # type: ignore
        sys.exit(1)

    if len(sys.argv) > 2:
        if sys.argv[1] == 'export':
            try:
                with open(sys.argv[2], 'wb') as export_:
                    pickle.dump(
                        udsactor.platform.store.readConfig(), export_, protocol=3
                    )
            except Exception as e:
                print('Error exporting configuration file: {}'.format(e))
                sys.exit(1)
            sys.exit(0)
        elif sys.argv[1] == 'import':
            try:
                with open(sys.argv[2], 'rb') as import_:
                    config = pickle.load(import_)  # nosec: B301: the file is provided by user, so it's not a security issue
                udsactor.platform.store.writeConfig(config)
            except Exception as e:
                print('Error importing configuration file: {}'.format(e))
                sys.exit(1)
            sys.exit(0)

    myapp = UDSConfigDialog()
    myapp.show()
    sys.exit(app.exec())
