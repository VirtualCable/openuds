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

import SimpleHTTPServer
import SocketServer
import threading
import uuid
import json
from base64 import decodestring
import time

from udsactor.log import logger
from udsactor import utils

startTime = time.time()


class HTTPServerHandler(SimpleHTTPServer.BaseHTTPServer.BaseHTTPRequestHandler):
    uuid = None
    ipc = None
    lock = threading.Lock()

    def sendJsonError(self, code, message):
        self.send_response(code)
        self.send_header('Content-type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}))
        return


    def do_GET(self):
        # Very simple path & params splitter
        path = self.path.split('?')[0][1:].split('/')
        try:
            params = dict((v.split('=') for v in self.path.split('?')[1].split('&')))
        except:
            params = {}

        if path[0] != HTTPServerHandler.uuid:
            self.sendJsonError(403, 'Forbidden')
            return

        if len(path) != 2:
            self.send_response(200)
            self.send_header('Content-type','application/json')
            self.end_headers()
            # Send the html message
            self.wfile.write(json.dumps("UDS Actor has been running for {} seconds".format(time.time() - startTime)))
            return

        try:
            operation = getattr(self, 'get_' + path[1])
            result = operation(params)  # Protect not POST methods
        except AttributeError:
            self.sendJsonError(404, 'Method not found')
            return
        except Exception as e:
            logger.error('Got exception executing GET {}: {}'.format(path[1], utils.toUnicode(e.message)))
            self.sendJsonError(500, unicode(e))
            return

        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        # Send the html message
        self.wfile.write(json.dumps(result))

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
            print length, ">>", content, '<<'
            params = json.loads(content)

            operation = getattr(self, 'post_' + path[1])
            result = operation(params)  # Protect not POST methods
        except AttributeError:
            self.sendJsonError(404, 'Method not found')
            return
        except Exception as e:
            logger.error('Got exception executing POST {}: {}'.format(path[1], utils.toUnicode(e.message)))
            self.sendJsonError(500, unicode(e))
            return
        finally:
            HTTPServerHandler.lock.release()


        self.send_response(200)
        self.send_header('Content-type','application/json')
        self.end_headers()
        # Send the html message
        self.wfile.write(json.dumps(result))

    def post_logoff(self, params):
        logger.debug('Sending LOGOFF to clients')
        HTTPServerHandler.ipc.sendLoggofMessage()

    # Alias
    post_logout = post_logoff

    def post_message(self, params):
        logger.debug('Sending MESSAGE to clients')
        if 'message' not in params:
            raise Exception('Invalid message parameters')
        HTTPServerHandler.ipc.sendMessageMessage(params['message'])

    def post_script(self, params):
        if 'script' not in params:
            raise Exception('Invalid script parameters')
        if 'user' in params:
            logger.debug('Sending SCRIPT to clients')
            HTTPServerHandler.ipc.sendScriptMessage(params['script'])
        else:
            # Execute script at server space, that is, here
            # as a secondary thread
            script = params['script']
            def executor():
                logger.debug('Executing script: {}'.format(script))
                try:
                    exec script in None, None
                except Exception as e:
                    logger.error('Error executing script: {}'.format(e))
            th = threading.Thread(target=executor)
            th.start()

    def get_information(self, params):
        # TODO: Return something useful? :)
        return 'Information'


class HTTPServerThread(threading.Thread):
    def __init__(self, address, ipc):
        super(self.__class__, self).__init__()

        if HTTPServerHandler.uuid is None:
            HTTPServerHandler.uuid =  uuid.uuid4().get_hex()

        HTTPServerHandler.ipc = ipc

        self.server = SocketServer.TCPServer(address, HTTPServerHandler)

    def getServerUrl(self):
        return 'http://{}:{}/{}'.format(self.server.server_address[0], self.server.server_address[1], HTTPServerHandler.uuid)

    def stop(self):
        self.server.shutdown()

    def run(self):
        self.server.serve_forever()
