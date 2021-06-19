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
import urllib
import urllib.parse
import urllib.request
import urllib.error
import ssl
import socket
import typing

from cryptography import x509
from cryptography.hazmat.backends import default_backend

from . import osDetector
from . import VERSION

# Callback for error on cert
# parameters are hostname, serial
# If returns True, ignores error
CertCallbackType = typing.Callable[[str, str], bool]


def _open(
    url: str, certErrorCallback: typing.Optional[CertCallbackType] = None
) -> typing.Any:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
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


def getUrl(
    url: str, certErrorCallback: typing.Optional[CertCallbackType] = None
) -> bytes:
    with _open(url, certErrorCallback) as response:
        resp = response.read()

    return resp


class RestRequest:

    restApiUrl: typing.ClassVar[str] = ''  # base Rest API URL
    _msgFunction: typing.Optional[CertCallbackType]
    _url: str

    def __init__(
        self,
        url,
        msgFunction: typing.Optional[CertCallbackType] = None,
        params: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> None:  # parent not used
        self._msgFunction = msgFunction

        if params:
            url += '?' + '&'.join(
                '{}={}'.format(k, urllib.parse.quote(str(v).encode('utf8')))
                for k, v in params.items()
            )

        self._url = RestRequest.restApiUrl + url

    def get(self) -> typing.Any:
        return json.loads(getUrl(self._url, self._msgFunction))

