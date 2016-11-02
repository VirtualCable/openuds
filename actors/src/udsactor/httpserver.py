# -*- coding: utf-8 -*-
#
# Copyright (c) 2014 Virtual Cable S.L.
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

from udsactor.log import logger
from udsactor import utils
from udsactor.certs import createSelfSignedCert
from udsactor.scriptThread import ScriptExecutorThread

import threading
import string
import random
import json
import six
from six.moves import socketserver  # @UnresolvedImport, pylint: disable=import-error
from six.moves import BaseHTTPServer  # @UnresolvedImport, pylint: disable=import-error
import time

import ssl

startTime = time.time()


class HTTPServerHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'
    server_version = 'UDS Actor Server'
    sys_version = ''

    uuid = None
    service = None
    lock = threading.Lock()

    def sendJsonError(self, code, message):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}))
        return

    def sendJsonResponse(self, data):
        self.send_response(200)
        data = json.dumps(data)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        # Send the html message
        self.wfile.write(data)

    def do_GET(self):
        # Very simple path & params splitter
        path = self.path.split('?')[0][1:].split('/')
        try:
            params = dict((v.split('=') for v in self.path.split('?')[1].split('&')))
        except Exception:
            params = {}

        if path[0] != HTTPServerHandler.uuid:
            self.sendJsonError(403, 'Forbidden')
            return

        if len(path) != 2:
            self.sendJsonResponse("UDS Actor has been running for {} seconds".format(time.time() - startTime))
            return

        try:
            operation = getattr(self, 'get_' + path[1])
            result = operation(params)  # Protect not POST methods
        except AttributeError:
            self.sendJsonError(404, 'Method not found')
            return
        except Exception as e:
            logger.error('Got exception executing GET {}: {}'.format(path[1], utils.toUnicode(e.message)))
            self.sendJsonError(500, str(e))
            return

        self.sendJsonResponse(result)

    def do_POST(self):
        path = self.path.split('?')[0][1:].split('/')
        if path[0] != HTTPServerHandler.uuid:
            self.sendJsonError(403, 'Forbidden')
            return

        if len(path) != 2:
            self.sendJsonError(400, 'Invalid request')
            return

        try:
            HTTPServerHandler.lock.acquire()
            length = int(self.headers.getheader('content-length'))
            content = self.rfile.read(length)
            logger.debug('length: {}, content >>{}<<'.format(length, content))
            params = json.loads(content)

            operation = getattr(self, 'post_' + path[1])
            result = operation(params)  # Protect not POST methods
        except AttributeError:
            self.sendJsonError(404, 'Method not found')
            return
        except Exception as e:
            logger.error('Got exception executing POST {}: {}'.format(path[1], utils.toUnicode(e.message)))
            self.sendJsonError(500, str(e))
            return
        finally:
            HTTPServerHandler.lock.release()

        self.sendJsonResponse(result)

    def post_logoff(self, params):
        logger.debug('Sending LOGOFF to clients')
        HTTPServerHandler.service.ipc.sendLoggofMessage()
        return 'ok'

    # Alias
    post_logout = post_logoff

    def post_message(self, params):
        logger.debug('Sending MESSAGE to clients')
        if 'message' not in params:
            raise Exception('Invalid message parameters')
        HTTPServerHandler.service.ipc.sendMessageMessage(params['message'])
        return 'ok'

    def post_script(self, params):
        logger.debug('Received script: {}'.format(params))
        if 'script' not in params:
            raise Exception('Invalid script parameters')
        if 'user' in params:
            logger.debug('Sending SCRIPT to clients')
            HTTPServerHandler.service.ipc.sendScriptMessage(params['script'])
        else:
            # Execute script at server space, that is, here
            # as a secondary thread
            th = ScriptExecutorThread(params['script'])
            th.start()
        return 'ok'

    def post_preConnect(self, params):
        logger.debug('Received Pre connection')
        if 'user' not in params or 'protocol' not in params:
            raise Exception('Invalid preConnect parameters')
        return HTTPServerHandler.service.preConnect(params.get('user'), params.get('protocol'))

    def get_information(self, params):
        # TODO: Return something useful? :)
        return 'Up and running'

    def get_uuid(self, params):
        return self.service.api.uuid

    def log_error(self, fmt, *args):
        logger.error('HTTP ' + fmt % args)

    def log_message(self, fmt, *args):
        logger.info('HTTP ' + fmt % args)


class HTTPServerThread(threading.Thread):
    def __init__(self, address, service):
        super(self.__class__, self).__init__()

        if HTTPServerHandler.uuid is None:
            HTTPServerHandler.uuid = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(48))

        self.certFile = createSelfSignedCert()
        HTTPServerHandler.service = service

        self.initiateServer(address)

    def getPort(self):
        return self.address[1]

    def getIp(self):
        return self.address[0]

    def initiateServer(self, address):
        self.address = (address[0], address[1])  # Copy address & keep it for future reference...

        addr = ('0.0.0.0', address[1])  # Adapt to listen on 0.0.0.0

        self.server = socketserver.TCPServer(addr, HTTPServerHandler)
        self.server.socket = ssl.wrap_socket(self.server.socket, certfile=self.certFile, server_side=True)

    def getServerUrl(self):
        return 'https://{}:{}/{}'.format(self.getIp(), self.getPort(), HTTPServerHandler.uuid)

    def stop(self):
        logger.debug('Stopping REST Service')
        self.server.shutdown()

    def restart(self, address=None):

        if address is None:
            # address = self.server.server_address
            address = self.address

        self.address = (address[0], self.address[1])  # Copy address & keep it for future reference, port is never changed once assigned on init

        # Listening on 0.0.0.0, does not need to restart listener..
        # self.stop()
        # self.initiateServer(address)

    def run(self):
        self.server.serve_forever()
