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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
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

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from . import os_detector
from . import tools
from . import VERSION
from .log import logger

# Server before this version uses "unsigned" scripts
OLD_METHOD_VERSION = '2.4.0'

SECURE_CIPHERS = (
    'TLS_AES_256_GCM_SHA384'
    ':TLS_CHACHA20_POLY1305_SHA256'
    ':TLS_AES_128_GCM_SHA256'
    ':ECDHE-RSA-AES256-GCM-SHA384'
    ':ECDHE-RSA-AES128-GCM-SHA256'
    ':ECDHE-RSA-CHACHA20-POLY1305'
    ':ECDHE-ECDSA-AES128-GCM-SHA256'
    ':ECDHE-ECDSA-AES256-GCM-SHA384'
    ':ECDHE-ECDSA-AES128-SHA256'
    ':ECDHE-ECDSA-CHACHA20-POLY1305'
)

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

    _restApiUrl: str  # base Rest API URL
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

    def get(
        self, url: str, params: typing.Optional[typing.Mapping[str, str]] = None
    ) -> typing.Any:
        if params:
            url += '?' + '&'.join(
                '{}={}'.format(k, urllib.parse.quote(str(v).encode('utf8')))
                for k, v in params.items()
            )

        return json.loads(
            RestApi.getUrl(self._restApiUrl + url, self._callbackInvalidCert)
        )

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
        except InvalidVersion:
            raise
        except Exception as e:
            raise UDSException(e)

    def getScriptAndParams(
        self, ticket: str, scrambler: str
    ) -> typing.Tuple[str, typing.Any]:
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
            raise Exception('Server version is too old. Please, update it')
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
        # Disable SSLv2, SSLv3, TLSv1, TLSv1.1
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.set_ciphers(SECURE_CIPHERS)

        # If we have the certificates file, we use it
        if tools.getCaCertsFile() is not None:
            ctx.load_verify_locations(tools.getCaCertsFile())
        hostname = urllib.parse.urlparse(url)[1]
        serial = ''

        port = ''
        if ':' in hostname:
            hostname, port = hostname.split(':')

        if url.startswith('https'):
            port = port or '443'
            with ctx.wrap_socket(
                socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                server_hostname=hostname,
            ) as s:
                s.connect((hostname, int(port)))
                # Get binary certificate
                binCert = s.getpeercert(True)
                if binCert:
                    cert = x509.load_der_x509_certificate(binCert, default_backend())
                else:
                    raise Exception('Certificate not found!')

            serial = hex(cert.serial_number)[2:]

        response = None
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.check_hostname = True

        def urlopen(url: str):
            # Generate the request with the headers
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': os_detector.getOs() + " - UDS Connector " + VERSION
                },
            )
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
