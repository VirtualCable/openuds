# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import threading
import http.server
import json
import time
import ssl
import typing

from ..log import logger
from .. import certs

from .public import PublicProvider
from .local import LocalProvider

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from ..service import CommonService
    from .handler import Handler

LISTEN_PORT = 43910

startTime = time.time()

class HTTPServerHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'UDS Actor Server'
    sys_version = ''

    _uuid: typing.Optional[str] = None
    _service: typing.Optional['CommonService'] = None

    def sendJsonResponse(self, result: typing.Optional[typing.Any] = None, error: typing.Optional[str] = None, code: int = 200) -> None:
        data = json.dumps({'result': result, 'error': error})
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Server: ', self.server_version)
        self.end_headers()
        self.wfile.write(data.encode())

    def process(self, method: str, params: typing.MutableMapping[str, str]) -> None:
        # Very simple path & params splitter
        path = self.path.split('?')[0][1:].split('/')

        handlerType: typing.Optional[typing.Type['Handler']] = None

        logger.debug('Path: {}, uuid: {}'.format(path, self._uuid))

        if len(path) == 3 and path[0] == 'actor' and path[1] == self._uuid:
            # public method
            handlerType = PublicProvider
        elif len(path) == 2 and path[0] == 'ui':
            # private method, only from localhost
            handlerType = LocalProvider

        if not handlerType or not self._service:
            self.sendJsonResponse(error='Forbidden', code=403)
            return

        try:
            result = getattr(handlerType(self._service, method, params), method + '_' + path[-1])()
        except AttributeError:
            self.sendJsonResponse(error='Method not found', code=404)
            return
        except Exception as e:
            logger.error('Got exception executing {} {}: {}'.format(method, '/'.join(path), str(e)))
            self.sendJsonResponse(error=str(e), code=500)
            return

        self.sendJsonResponse(result)

    def do_GET(self) -> None:
        try:
            params = {v.split('=')[0]: v.split('=')[1] for v in self.path.split('?')[1].split('&')}
        except Exception:
            params = {}

        self.process('get', params)


    def do_POST(self) -> None:
        try:
            length = int(str(self.headers.get('content-length', '0')))
            content = self.rfile.read(length)
            logger.debug('length: {}, content >>{}<<'.format(length, content))
            params: typing.MutableMapping[str, str] = json.loads(content)
        except Exception as e:
            logger.error('Got exception executing POST {}: {}'.format(self.path, str(e)))
            self.sendJsonResponse(error=str(e), code=500)
            return

        self.process('post', params)

    def log_error(self, format, *args):  # pylint: disable=redefined-builtin
        logger.error('ERROR ' + format % args)

    def log_message(self, format, *args):  # pylint: disable=redefined-builtin
        logger.info('INFO  ' + format % args)


class HTTPServerThread(threading.Thread):
    _server: http.server.HTTPServer

    def __init__(self, service: 'CommonService'):
        super().__init__()

        HTTPServerHandler._uuid = service._cfg.own_token  # pylint: disable=protected-access
        HTTPServerHandler._service = service  # pylint: disable=protected-access

        self.certFile = certs.createSelfSignedCert()
        self._server = http.server.HTTPServer(('0.0.0.0', LISTEN_PORT), HTTPServerHandler)
        self._server.socket = ssl.wrap_socket(self._server.socket, certfile=self.certFile, server_side=True)

    def stop(self) -> None:
        logger.debug('Stopping REST Service')
        self._server.shutdown()

    def run(self):
        self._server.serve_forever()
