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
# pylint: disable=c-extension-no-member,no-name-in-module

import json
import bz2
import base64
import urllib
import urllib.parse
import urllib.request
import urllib.error
import ssl
import socket
import typing

import certifi
from cryptography import x509
from cryptography.hazmat.backends import default_backend

from . import osDetector
from . import tools
from . import VERSION
from .log import logger

# Server before this version uses "unsigned" scripts
OLD_METHOD_VERSION = '2.4.0'

# Callback for error on cert
# parameters are hostname, serial
# If returns True, ignores error
CertCallbackType = typing.Callable[[str, str], bool]

# Exceptions
class UDSException(Exception):
    pass

class RetryException(UDSException):
    pass

class InvalidVersion(UDSException):
    downloadUrl: str

    def __init__(self, downloadUrl: str) -> None:
        super().__init__(downloadUrl)
        self.downloadUrl = downloadUrl

class RestApi:

    _restApiUrl: str      # base Rest API URL
    _callbackInvalidCert: typing.Optional[CertCallbackType]
    _serverVersion: str

    def __init__(
        self,
        restApiUrl,
        callbackInvalidCert: typing.Optional[CertCallbackType] = None,
    ) -> None:  # parent not used
        logger.debug('Setting request URL to %s', restApiUrl)

        self._restApiUrl = restApiUrl
        self._callbackInvalidCert = callbackInvalidCert
        self._serverVersion = ''

    def get(self, url: str, params: typing.Optional[typing.Mapping[str, str]] = None) -> typing.Any:
        if params:
            url += '?' + '&'.join(
                '{}={}'.format(k, urllib.parse.quote(str(v).encode('utf8')))
                for k, v in params.items()
            )

        return json.loads(RestApi.getUrl(self._restApiUrl + url, self._callbackInvalidCert))

    def processError(self, data: typing.Any) -> None:
        if 'error' in data:
            if data.get('retryable', '0') == '1':
                raise RetryException(data['error'])

            raise UDSException(data['error'])


    def getVersion(self) -> str:
        '''Gets and stores the serverVersion.
        Also checks that the version is valid for us. If not,
        will raise an "InvalidVersion' exception'''

        downloadUrl = ''
        if not self._serverVersion:
            data = self.get('')
            self.processError(data)
            self._serverVersion = data['result']['requiredVersion']
            downloadUrl = data['result']['downloadUrl']

        try:
            if self._serverVersion > VERSION:
                raise InvalidVersion(downloadUrl)
            
            return self._serverVersion
        except Exception as e:
            raise UDSException(e)

    def getScriptAndParams(self, ticket: str, scrambler: str) -> typing.Tuple[str, typing.Any]:
        '''Gets the transport script, validates it if necesary
        and returns it'''
        try:
            data = self.get(
                '/{}/{}'.format(ticket, scrambler),
                params={'hostname': tools.getHostName(), 'version': VERSION},
            )
        except Exception as e:
            logger.exception('Got exception on getTransportData')
            raise e

        logger.debug('Transport data received')
        self.processError(data)

        params = None

        if self._serverVersion <= OLD_METHOD_VERSION:
            script = bz2.decompress(base64.b64decode(data['result']))
            # This fixes uds 2.2 "write" string on binary streams on some transport
            script = script.replace(b'stdin.write("', b'stdin.write(b"')
            script = script.replace(b'version)', b'version.decode("utf-8"))')
        else:
            res = data['result']
            # We have three elements on result:
            # * Script
            # * Signature
            # * Script data
            # We test that the Script has correct signature, and them execute it with the parameters
            # script, signature, params = res['script'].decode('base64').decode('bz2'), res['signature'], json.loads(res['params'].decode('base64').decode('bz2'))
            script, signature, params = (
                bz2.decompress(base64.b64decode(res['script'])),
                res['signature'],
                json.loads(bz2.decompress(base64.b64decode(res['params']))),
            )
            if tools.verifySignature(script, signature) is False:
                logger.error('Signature is invalid')

                raise Exception(
                    'Invalid UDS code signature. Please, report to administrator'
                )

        return script.decode(), params

        # exec(script.decode("utf-8"), globals(), {'parent': self, 'sp': params})


    @staticmethod
    def _open(
        url: str, certErrorCallback: typing.Optional[CertCallbackType] = None
    ) -> typing.Any:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_verify_locations(certifi.where())
        hostname = urllib.parse.urlparse(url)[1]
        serial = ''

        if url.startswith('https'):
            with ctx.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM), server_hostname=hostname
            ) as s:
                s.connect((hostname, 443))
                # Get binary certificate
                binCert = s.getpeercert(True)
                if binCert:
                    cert = x509.load_der_x509_certificate(binCert, default_backend())
                else:
                    raise Exception('Certificate not found!')

            serial = hex(cert.serial_number)[2:]

        response = None
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED

        def urlopen(url: str):
            # Generate the request with the headers
            req = urllib.request.Request(url, headers={
                'User-Agent': osDetector.getOs() + " - UDS Connector " + VERSION
            })
            return urllib.request.urlopen(req, context=ctx)

        try:
            response = urlopen(url)
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                # Ask about invalid certificate
                if certErrorCallback:
                    if certErrorCallback(hostname, serial):
                        ctx.check_hostname = False
                        ctx.verify_mode = ssl.CERT_NONE
                        response = urlopen(url)
                else:
                    raise
            else:
                raise

        return response

    @staticmethod
    def getUrl(
        url: str, certErrorCallback: typing.Optional[CertCallbackType] = None
    ) -> bytes:
        with RestApi._open(url, certErrorCallback) as response:
            resp = response.read()

        return resp
