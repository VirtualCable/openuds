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
import cPickle

from udsactor.utils import toUnicode
from udsactor.log import logger

# The IPC Server will wait for connections from clients
# Clients will open socket, and wait for data from server
# The messages sent will be the following (subject to future changes):
#     Message_id     Data               Action
#    ------------  --------         --------------------------
#    MSG_LOGOFF     None            Logout user from session
#    MSG_MESSAGE    message,level   Display a message with level (INFO, WARN, ERROR, FATAL)     # TODO: Include levle, right now only has message
#    MSG_SCRIPT     python script   Execute an specific python script INSIDE CLIENT environment (this messages is not sent right now)
#
# All messages are in the form:
# BYTE
#  0           1-2                        3 4 ...
# MSG_ID   DATA_LENGTH (little endian)    Data (can be 0 length)
# With a previos "MAGIC" header in fron of each message

MSG_LOGOFF = 0xA1
MSG_MESSAGE = 0xB2
MSG_SCRIPT = 0xC3
MSG_INFORMATION = 0x90

VALID_MESSAGES = (MSG_LOGOFF, MSG_MESSAGE, MSG_SCRIPT, MSG_INFORMATION)

REQ_INFORMATION = 0xAA

MAGIC = b'\x55\x44\x53\x00'  # UDS in hexa with a padded 0 to the ridght

class ClientProcessor(threading.Thread):
    def __init__(self, parent, clientSocket):
        super(self.__class__, self).__init__()
        self.parent = parent
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
                    if buf == b'':  # No data
                        break
                    for b in buf:
                        if ord(b) == REQ_INFORMATION:
                            infoParams = self.parent.infoParams if self.parent.infoParams is not None else {}
                            self.messages.put((MSG_INFORMATION, cPickle.dumps(infoParams)))
                            logger.debug('Received a request for information')
                        else:
                            logger.debug('Got unexpected data {}'.format(ord(b)))
                # In fact, we do not process anything right now, simply empty recv buffer if something is found
            except socket.error as e:
                # If no data is present, no problem at all
                pass

            try:
                msg = self.messages.get(block=True, timeout=1)
            except Queue.Empty:  # No message got in time
                continue

            logger.debug('Got message {}'.format(msg))

            try:
                m = msg[1] if msg[1] is not None else b''
                l = len(m)
                data = MAGIC + chr(msg[0]) + chr(l&0xFF) + chr(l>>8) + m
                try:
                    self.clientSocket.sendall(data)
                except socket.error as e:
                    # Send data error
                    logger.debug('Socket connection is no more available: {}'.format(toUnicode(e)))
                    self.running = False
            except Exception as e:
                logger.error('Invalid message in queue: {}'.format(e))

        try:
            self.clientSocket.close()
        except Exception:
            pass  # If can't close, nothing happens, just end thread


class ServerIPC(threading.Thread):

    def __init__(self, listenPort, infoParams=None):
        super(self.__class__, self).__init__()
        self.port = listenPort
        self.running = False
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.threads = []
        self.infoParams = infoParams

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

        # Convert to bytes so length is correctly calculated
        if isinstance(msgData, unicode):
            msgData = msgData.encode('utf8')

        for t in self.threads:
            if t.isAlive():
                logger.debug('Sending to {}'.format(t))
                t.messages.put((msgId, msgData))

    def cleanupFinishedThreads(self):
        '''
        Cleans up current threads list
        '''
        aliveThreads = []
        for t in self.threads:
            if t.isAlive():
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

                self.cleanupFinishedThreads()  # House keeping

                t = ClientProcessor(self, clientSocket)
                self.threads.append(t)
                t.start()
            except Exception as e:
                logger.error('Got an exception on Server ipc thread: {}'.format(e))


class ClientIPC(threading.Thread):
    def __init__(self, listenPort):
        super(ClientIPC, self).__init__()
        self.port = listenPort
        self.running = False
        self.clientSocket = None
        self.messages = Queue.Queue(32)

        self.connect()

    def stop(self):
        self.running = False

    def getMessage(self):
        while self.running:
            try:
                return self.messages.get(timeout=1)
            except Queue.Empty:
                continue

        return None

    def requestInformation(self):
        self.clientSocket.sendall(chr(REQ_INFORMATION))

    def messageReceived(self):
        '''
        Override this method to automatically get notified on new message
        received. Message is at self.messages queue
        '''
        pass # Messa

    def receiveBytes(self, number):
        msg = b''
        while self.running and len(msg) < number:
            try:
                buf = self.clientSocket.recv(number-len(msg))
                if buf == b'':
                    self.running = False
                    break
                msg += buf
            except socket.timeout:
                pass

        if self.running is False:
            return None
        return msg

    def connect(self):
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clientSocket.connect(('localhost', self.port))
        self.clientSocket.settimeout(2)  # 2 seconds timeout

    def run(self):
        self.running = True

        while self.running:
            try:
                msg = b''
                # We look for magic message header
                while self.running:  # Wait for MAGIC
                    try:
                        buf = self.clientSocket.recv(len(MAGIC)-len(msg))
                        if buf == b'':
                            self.running = False
                            break
                        msg += buf
                        if len(msg) != len(MAGIC):
                            continue  # Do not have message
                        if msg != MAGIC:  # Skip first byte an continue searchong
                            msg = msg[1:]
                            continue
                        break
                    except socket.timeout: # Timeout is here so we can get stop thread
                        continue

                # Now we get message basic data (msg + datalen)
                msg = self.receiveBytes(3)

                # We have the magic header, here comes the message itself
                if msg is None:
                    continue

                msgId = ord(msg[0])
                dataLen = ord(msg[1]) + (ord(msg[2])<<8)
                if msgId not in VALID_MESSAGES:
                    raise Exception('Invalid message id: {}'.format(msgId))

                data = self.receiveBytes(dataLen)
                if data is None:
                    continue

                self.messages.put((msgId, data))
                self.messageReceived()

            except socket.error as e:
                logger.error('Communication with server got an error: {}'.format(toUnicode(e.strerror)))
                self.running = False
                return
            except Exception as e:
                logger.error('Error: {}'.format(toUnicode(e.message)))

        try:
            self.clientSocket.close()
        except Exception:
            pass  # If can't close, nothing happens, just end thread

