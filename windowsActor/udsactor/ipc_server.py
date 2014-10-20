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

import socket
import threading
import Queue
import time

from udsactor.utils import toUnicode
from udsactor.log import logger

# The IPC Server will wait for connections from clients
# Clients will open socket, and wait for data from server
# The messages sent will be the following (subject to future changes):
#     Message_id     Data               Action
#    ------------  --------         --------------------------
#    MSG_LOGOFF     None            Logout user from session
#    MSG_MESSAGE    message,level   Display a message with level (INFO, WARN, ERROR, FATAL)
#    MSG_SCRIPT     python script   Execute an specific python script INSIDE CLIENT environment (this messages is not sent right now)
#
# All messages are in the form:
# BYTE
#  0           1-2                        3 4 ...
# MSG_ID   DATA_LENGTH (little endian)    Data (can be 0 length)

MSG_LOGOFF = 0
MSG_MESSAGE = 1
MSG_SCRIPT = 2

class ClientProcessor(threading.Thread):
    def __init__(self, clientSocket):
        super(self.__class__, self).__init__()
        self.clientSocket = clientSocket
        self.running = False
        self.messages = Queue.Queue(32)

    def stop(self):
        logger.debug('Stoping client processor')
        self.running = False

    def run(self):
        self.running = True
        self.clientSocket.setblocking(0)

        while self.running:
            try:
                while True:
                    buf = self.clientSocket.recv(512)   # Empty buffer, this is set as non-blocking
                    if buf == '':
                        break
                    logger.debug('Got unexpected data {}'.format(buf))
                # In fact, we do not process anything right now, simply empty recv buffer if something is found
            except socket.error as e:
                logger.debug('Got socket error {}'.format(toUnicode(e.strerror)))
                # If no data is present
                pass

            try:
                msg = self.messages.get(block=True, timeout=1)
            except Queue.Empty:  # No message got in time
                continue

            logger.debug('Got message {}'.format(msg))

            try:
                m = msg[1] if msg[1] is not None else ''
                l = len(m)
                data = chr(msg[0]) + chr(l/256) + chr(l&0xFF) + m.encode('utf8', 'ignore')
                try:
                    self.clientSocket.sendall(data)
                except socket.error as e:
                    # Send data error
                    logger.info('Socket connection is no more available: {}'.format(toUnicode(e.strerror)))
                    self.running = False
            except Exception as e:
                logger.error('Invalid message in queue: {}'.format(toUnicode(e.strerror)))
        try:
            self.clientSocket.close()
        except Exception:
            pass  # If can't close, nothing happens, just end thread


class ServerIPC(threading.Thread):

    def __init__(self, listenPort):
        super(self.__class__, self).__init__()
        self.port = listenPort
        self.running = False
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.threads = []

    def stop(self):
        logger.debug('Stopping Server IPC')
        self.running = False
        for t in self.threads:
            t.stop()
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(('localhost', self.port))
        self.serverSocket.close()

        for t in self.threads:
            t.join()

    def sendMessage(self, msgId, msgData):
        '''
        Notify message to all listening threads
        '''
        logger.debug('Sending message {},{} to all clients'.format(msgId, msgData))
        for t in self.threads:
            logger.debug('Sending to {}'.format(t))
            t.messages.put((msgId, msgData))

    def cleanupFinishedThreads(self):
        '''
        Cleans up current threads list
        '''
        aliveThreads = []
        for t in self.threads:
            if t.isAlive() is True:
                logger.debug('Thread {} is alive'.format(t))
                aliveThreads.append(t)
        self.threads[:] = aliveThreads

    def run(self):
        self.running = True

        self.serverSocket.bind(('localhost', self.port))
        self.serverSocket.setblocking(1)
        self.serverSocket.listen(4)

        while True:
            try:
                (clientSocket, address) = self.serverSocket.accept()
                # Stop processiong if thread is mean to stop
                if self.running is False:
                    break
                logger.debug('Got connection from {}'.format(address))

                self.cleanupFinishedThreads()

                t = ClientProcessor(clientSocket)
                self.threads.append(t)
                t.start()
            except Exception as e:
                logger.error('Got an exception on Server ipc thread: {}'.format(e))
