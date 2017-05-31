# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
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

from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PyQt4.QtCore import QObject, QUrl, QSettings
from PyQt4.QtCore import Qt
from PyQt4.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply, QSslCertificate
from PyQt4.QtGui import QMessageBox
from . import VERSION

import json
import osDetector
import six
import urllib


class RestRequest(QObject):

    restApiUrl = ''  #

    done = pyqtSignal(dict, name='done')

    def __init__(self, url, parentWindow, done, params=None):  # parent not used
        super(RestRequest, self).__init__()
        # private
        self._manager = QNetworkAccessManager()
        if params is not None:
            url += '?' + '&'.join('{}={}'.format(k, urllib.quote(six.text_type(v).encode('utf8'))) for k, v in params.iteritems())

        self.url = QUrl(RestRequest.restApiUrl + url)

        # connect asynchronous result, when a request finishes
        self._manager.finished.connect(self._finished)
        self._manager.sslErrors.connect(self._sslError)
        self._parentWindow = parentWindow

        self.done.connect(done, Qt.QueuedConnection)

    # private slot, no need to declare as slot
    @pyqtSlot(QNetworkReply)
    def _finished(self, reply):
        '''
        Handle signal 'finished'.  A network request has finished.
        '''
        try:
            if reply.error() != QNetworkReply.NoError:
                raise Exception(reply.errorString())
            data = six.text_type(reply.readAll())
            data = json.loads(data)
        except Exception as e:
            data = {
                'result': None,
                'error': six.text_type(e)
            }

        self.done.emit(data)

        reply.deleteLater()  # schedule for delete from main event loop

    @pyqtSlot(QNetworkReply, list)
    def _sslError(self, reply, errors):
        settings = QSettings()
        settings.beginGroup('ssl')
        cert = errors[0].certificate()
        digest = six.text_type(cert.digest().toHex())

        approved = settings.value(digest, False).toBool()

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
        request.setRawHeader('User-Agent', osDetector.getOs() + " - UDS Connector " + VERSION)
        self._manager.get(request)
