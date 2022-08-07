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
# pylint: disable=invalid-name
import threading
import http.server
import secrets
import json
import typing

from ..log import logger

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from ..client import UDSActorClient

class HTTPServerHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'UDS Actor Server'
    sys_version = ''

    _id: typing.ClassVar[str]  # Random id for server
    _app: typing.ClassVar['UDSActorClient']

    def sendJsonResponse(self, result: typing.Optional[typing.Any] = None, error: typing.Optional[str] = None, code: int = 200) -> None:
        data = json.dumps({'result': result, 'error': error})
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Server: ', self.server_version)
        self.end_headers()
        try:
            self.wfile.write(data.encode())
        except Exception:
            pass  # Evict "broken pipe" when sending errors

    def do_POST(self) -> None:
        # Only allows requests from localhost
        if self.client_address[0][:3] != '127':
            self.sendJsonResponse(error='Forbidden', code=403)

        # Very simple path & params splitter
        path = self.path.split('?')[0][1:].split('/')
        if len(path) != 2 or path[0] != HTTPServerHandler._id:
            self.sendJsonResponse(error='Forbidden', code=403)

        try:
            length = int(str(self.headers.get('content-length', '0')))
            content = self.rfile.read(length)
            params: typing.MutableMapping[str, str] = json.loads(content or '{}')
        except Exception as e:
            logger.error('Got exception executing POST {}: {}'.format(self.path, str(e)))
            self.sendJsonResponse(error='Invalid request', code=400)
            return

        try:
            result = getattr(self, 'method_' + path[1])(params)  # last part of path is method
        except AttributeError as e:
            logger.error('Invoked invalid method: %s: %s', path[1], e)
            self.sendJsonResponse(error='Invalid request', code=400)
            return
        except Exception as e:
            logger.error('Got exception executing {}: {}'.format('/'.join(path), str(e)))
            self.sendJsonResponse(error='Internal error', code=500)
            return

        self.sendJsonResponse(result)

    # Internal methods
    def method_ping(self, params: typing.MutableMapping[str, str]) -> typing.Any:
        return 'pong'

    def method_logout(self, params: typing.MutableMapping[str, str]) -> typing.Any:
        return self._app.logout()

    def method_message(self, params: typing.MutableMapping[str, str]) -> typing.Any:
        return self._app.message(params['message'])

    def method_screenshot(self, params: typing.MutableMapping[str, str]) -> typing.Any:
        return self._app.screenshot()

    def method_script(self, params: typing.MutableMapping[str, str]) -> typing.Any:
        return self._app.script(params['script'])

    def do_GET(self) -> None:
        self.sendJsonResponse(error='Forbidden', code=403)

    def log_error(self, format: str, *args):  # pylint: disable=redefined-builtin
        logger.error(format, *args)

    def log_message(self, format: str, *args):  # pylint: disable=redefined-builtin
        logger.debug(format, *args)

class HTTPServerThread(threading.Thread):
    _server: typing.Optional[http.server.HTTPServer]
    _app: 'UDSActorClient'

    port: int
    id: str

    def __init__(self, app: 'UDSActorClient'):
        super().__init__()

        self._server = None
        self._app = app

        self.port = -1
        self.id = secrets.token_urlsafe(24)

    @property
    def url(self) -> str:
        return 'http://127.0.0.1:{}/{}'.format(self.port, self.id)

    def stop(self) -> None:
        if self._server:
            logger.debug('Stopping Http-client Service')
            try:
                self._app.api.unregister(self.url)
            except Exception as e:
                logger.error('Error unregistering on actor service: %s', e)
            self._server.shutdown()
            self._server = None

    def run(self):
        HTTPServerHandler._app = self._app  # pylint: disable=protected-access
        HTTPServerHandler._id = self.id  # pylint: disable=protected-access

        self._server = http.server.HTTPServer(('127.0.0.1', 0), HTTPServerHandler)

        self.port = self._server.socket.getsockname()[1]

        # Register using app api
        logger.debug('Registered %s', self.url)
        try:
            self._app.api.register(self.url)
        except Exception as e:
            logger.error('Error registering on actor service: %s', e)

        self._server.serve_forever()
