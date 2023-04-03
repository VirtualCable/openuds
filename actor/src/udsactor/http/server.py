# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Virtual Cable S.L.
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
import os
import threading
import http.server
import json
import ssl
import typing

from ..log import logger
from .. import certs
from .. import rest

from .public import PublicProvider
from .local import LocalProvider

# a couple of 1.2 ciphers + 1.3 ciphers (implicit)
DEFAULT_CIPHERS = (
    'ECDHE-RSA-AES128-GCM-SHA256'
    ':ECDHE-RSA-AES256-GCM-SHA384'
)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from ..service import CommonService
    from .handler import Handler


class HTTPServerHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'UDS Actor Server'
    sys_version = ''

    _service: typing.Optional['CommonService'] = None

    def sendJsonResponse(
        self,
        result: typing.Optional[typing.Any] = None,
        error: typing.Optional[str] = None,
        code: int = 200,
    ) -> None:
        data = json.dumps({'result': result, 'error': error})
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Server: ', self.server_version)
        self.end_headers()
        self.wfile.write(data.encode())

    def process(self, method: str, params: typing.MutableMapping[str, str]) -> None:
        if not self._service:
            self.sendJsonResponse(error='Not initialized', code=500)
            return

        # Very simple path & params splitter
        path = self.path.split('?')[0][1:].split('/')

        logger.debug('Path: %s, ip: %s, params: %s', path, self.client_address, params)

        handlerType: typing.Optional[typing.Type['Handler']] = None

        if (
            len(path) == 3 and path[0] == 'actor' and path[1] == self._service._secret
        ):  # pylint: disable=protected-access
            # public method
            handlerType = PublicProvider
        elif len(path) == 2 and path[0] == 'ui':
            # private method, only from localhost
            if self.client_address[0][:3] == '127':
                handlerType = LocalProvider

        if not handlerType:
            self.sendJsonResponse(error='Forbidden', code=403)
            return

        try:
            result = getattr(
                handlerType(self._service, method, params), method + '_' + path[-1]
            )()  # last part of path is method
        except AttributeError:
            self.sendJsonResponse(error='Method not found', code=404)
            return
        except Exception as e:
            logger.error(
                'Got exception executing {} {}: {}'.format(
                    method, '/'.join(path), str(e)
                )
            )
            self.sendJsonResponse(error=str(e), code=500)
            return

        self.sendJsonResponse(result)

    def do_GET(self) -> None:
        try:
            params = {
                v.split('=')[0]: v.split('=')[1]
                for v in self.path.split('?')[1].split('&')
            }
        except Exception:
            params = {}

        self.process('get', params)

    def do_POST(self) -> None:
        try:
            length = int(str(self.headers.get('content-length', '0')))
            content = self.rfile.read(length)
            params: typing.MutableMapping[str, str] = json.loads(content)
        except Exception as e:
            logger.error(
                'Got exception executing POST {}: {}'.format(self.path, str(e))
            )
            self.sendJsonResponse(error='Invalid parameters', code=400)
            return

        self.process('post', params)

    def log_error(self, format, *args):  # pylint: disable=redefined-builtin
        logger.error(format, *args)

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        logger.debug(format, *args)


class HTTPServerThread(threading.Thread):
    _server: typing.Optional[http.server.HTTPServer]
    _service: 'CommonService'
    _certFile: typing.Optional[str]

    def __init__(self, service: 'CommonService'):
        super().__init__()

        self._server = None
        self._service = service
        self._certFile = None

    def stop(self) -> None:
        logger.debug('Stopping Http-server Service')
        if self._server:
            self._server.shutdown()
            self._server = None

        if self._certFile:
            try:
                os.unlink(self._certFile)
            except Exception as e:
                logger.error('Error removing certificate file: %s', e)
        logger.debug('Http-server stopped')

    def run(self):
        HTTPServerHandler._service = self._service  # pylint: disable=protected-access

        self._certFile, password = certs.saveCertificate(
            self._service._certificate
        )  # pylint: disable=protected-access

        self._server = http.server.HTTPServer(
            ('0.0.0.0', rest.LISTEN_PORT), HTTPServerHandler
        )
        # self._server.socket = ssl.wrap_socket(self._server.socket, certfile=self.certFile, server_side=True)

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        # Disable TLSv1.0 and TLSv1.1, use only TLSv1.3 or TLSv1.2 with allowed ciphers
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        # If a configures ciphers are provided, use them, otherwise use the default ones
        context.set_ciphers(self._service._certificate.ciphers or DEFAULT_CIPHERS)

        context.load_cert_chain(certfile=self._certFile, password=password)
        self._server.socket = context.wrap_socket(self._server.socket, server_side=True)

        self._server.serve_forever()
