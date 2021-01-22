# -*- coding: utf-8 -*-
#
# Copyright (c) 2017-2021 Virtual Cable S.L.U.
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
# pylint: disable=c-extension-no-member,no-name-in-module

import json
import urllib
import urllib.parse

import certifi

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import QObject, QUrl, QSettings
from PyQt5.QtCore import Qt
from PyQt5.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QSslCertificate
from PyQt5.QtWidgets import QMessageBox

from . import os_detector

from . import VERSION



class RestRequest(QObject):

    restApiUrl = ''  #

    done = pyqtSignal(dict, name='done')

    def __init__(self, url, parentWindow, done, params=None):  # parent not used
        super(RestRequest, self).__init__()
        # private
        self._manager = QNetworkAccessManager()


        if params is not None:
            url += '?' + '&'.join('{}={}'.format(k, urllib.parse.quote(str(v).encode('utf8'))) for k, v in params.items())

        self.url = QUrl(RestRequest.restApiUrl + url)

        # connect asynchronous result, when a request finishes
        self._manager.finished.connect(self._finished)
        self._manager.sslErrors.connect(self._sslError)
        self._parentWindow = parentWindow

        self.done.connect(done, Qt.QueuedConnection)

    def _finished(self, reply):
        '''
        Handle signal 'finished'.  A network request has finished.
        '''
        try:
            if reply.error() != QNetworkReply.NoError:
                raise Exception(reply.errorString())
            data = bytes(reply.readAll())
            data = json.loads(data)
        except Exception as e:
            data = {
                'result': None,
                'error': str(e)
            }

        self.done.emit(data)

        reply.deleteLater()  # schedule for delete from main event loop

    def _sslError(self, reply, errors):
        settings = QSettings()
        settings.beginGroup('ssl')
        cert = errors[0].certificate()
        digest = str(cert.digest().toHex())

        approved = settings.value(digest, False)

        errorString = '<p>The certificate for <b>{}</b> has the following errors:</p><ul>'.format(cert.subjectInfo(QSslCertificate.CommonName))

        for err in errors:
            errorString += '<li>' + err.errorString() + '</li>'

        errorString += '</ul>'

        if approved or QMessageBox.warning(self._parentWindow, 'SSL Warning', errorString, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            settings.setValue(digest, True)
            reply.ignoreSslErrors()

        settings.endGroup()

    def get(self):
        request = QNetworkRequest(self.url)
        # Ensure loads certifi certificates
        sslCfg = request.sslConfiguration()
        sslCfg.addCaCertificates(certifi.where())
        request.setSslConfiguration(sslCfg)
        request.setRawHeader(b'User-Agent', os_detector.getOs().encode('utf-8') + b" - UDS Connector " + VERSION.encode('utf-8'))
        self._manager.get(request)
