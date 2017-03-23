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
import sys
import six
import traceback
import pickle
import errno
import time

from udsactor.utils import toUnicode
from udsactor.log import logger

# The IPC Server will wait for connections from clients
# Clients will open socket, and wait for data from server
# The messages sent (from server) will be the following (subject to future changes):
#     Message_id     Data               Action
#    ------------  --------         --------------------------
#    MSG_LOGOFF     None            Logout user from session
#    MSG_MESSAGE    message,level   Display a message with level (INFO, WARN, ERROR, FATAL)     # TODO: Include level, right now only has message
#    MSG_SCRIPT     python script   Execute an specific python script INSIDE CLIENT environment (this messages is not sent right now)
# The messages received (sent from client) will be the following:
#     Message_id       Data               Action
#    ------------    --------         --------------------------
#    REQ_LOGOUT                   Logout user from session
#    REQ_INFORMATION  None            Request information from ipc server (maybe configuration parameters in a near future)
#    REQ_LOGIN        python script   Execute an specific python script INSIDE CLIENT environment (this messages is not sent right now)
#
# All messages are in the form:
# BYTE
#  0           1-2                        3 4 ...
# MSG_ID   DATA_LENGTH (little endian)    Data (can be 0 length)
# With a previos "MAGIC" header in fron of each message

MSG_LOGOFF = 0xA1
MSG_MESSAGE = 0xB2
MSG_SCRIPT = 0xC3
MSG_INFORMATION = 0xD4

# Request messages
REQ_INFORMATION = MSG_INFORMATION
REQ_LOGIN = 0xE5
REQ_LOGOUT = MSG_LOGOFF

VALID_MESSAGES = (MSG_LOGOFF, MSG_MESSAGE, MSG_SCRIPT, MSG_INFORMATION)

REQ_INFORMATION = 0xAA

# Reverse msgs dict for debugging
REV_DICT = {
    MSG_LOGOFF: 'MSG_LOGOFF',
    MSG_MESSAGE: 'MSG_MESSAGE',
    MSG_SCRIPT: 'MSG_SCRIPT',
    MSG_INFORMATION: 'MSG_INFORMATION',
    REQ_LOGIN: 'REQ_LOGIN',
    REQ_LOGOUT: 'REQ_LOGOUT'
}

MAGIC = b'\x55\x44\x53\x00'  # UDS in hexa with a padded 0 to the right


# Allows notifying login/logout from client for linux platform
ALLOW_LOG_METHODS = sys.platform != 'win32'


# States for client processor
ST_SECOND_BYTE = 0x01
ST_RECEIVING = 0x02
ST_PROCESS_MESSAGE = 0x02


class ClientProcessor(threading.Thread):
    def __init__(self, parent, clientSocket):
        super(self.__class__, self).__init__()
        self.parent = parent
        self.clientSocket = clientSocket
        self.running = False
        self.messages = six.moves.queue.Queue(32)  # @UndefinedVariable

    def stop(self):
        logger.debug('Stoping client processor')
        self.running = False

    def processRequest(self, msg, data):
        logger.debug('Got Client message {}={}'.format(msg, REV_DICT.get(msg)))
        if self.parent.clientMessageProcessor is not None:
            self.parent.clientMessageProcessor(msg, data)

    def run(self):
        self.running = True
        self.clientSocket.setblocking(0)

        state = None
        recv_msg = None
        recv_data = None
        while self.running:
            try:
                counter = 1024
                while counter > 0:  # So we process at least the incoming queue every XX bytes readed
                    counter -= 1
                    b = self.clientSocket.recv(1)
                    if b == b'':
                        # Client disconnected
                        self.running = False
                        break
                    buf = six.byte2int(b)  # Empty buffer, this is set as non-blocking
                    if state is None:
                        if buf in (REQ_INFORMATION, REQ_LOGIN, REQ_LOGOUT):
                            logger.debug('State set to {}'.format(buf))
                            state = buf
                            recv_msg = buf
                            continue  # Get next byte
                        else:
                            logger.debug('Got unexpected data {}'.format(buf))
                    elif state in (REQ_INFORMATION, REQ_LOGIN, REQ_LOGOUT):
                        logger.debug('First length byte is {}'.format(buf))
                        msg_len = buf
                        state = ST_SECOND_BYTE
                        continue
                    elif state == ST_SECOND_BYTE:
                        msg_len += buf << 8
                        logger.debug('Second length byte is {}, len is {}'.format(buf, msg_len))
                        if msg_len == 0:
                            self.processRequest(recv_msg, None)
                            state = None
                            break
                        state = ST_RECEIVING
                        recv_data = b''
                        continue
                    elif state == ST_RECEIVING:
                        recv_data += six.int2byte(buf)
                        msg_len -= 1
                        if msg_len == 0:
                            self.processRequest(recv_msg, recv_data)
                            recv_data = None
                            state = None
                            break
                    else:
                        logger.debug('Got invalid message from request: {}, state: {}'.format(buf, state))
            except socket.error as e:
                # If no data is present, no problem at all, pass to check messages
                pass
            except Exception as e:
                tb = traceback.format_exc()
                logger.error('Error: {}, trace: {}'.format(e, tb))

            if self.running is False:
                break

            try:
                msg = self.messages.get(block=True, timeout=1)
            except six.moves.queue.Empty:  # No message got in time @UndefinedVariable
                continue

            logger.debug('Got message {}={}'.format(msg, REV_DICT.get(msg)))

            try:
                m = msg[1] if msg[1] is not None else b''
                l = len(m)
                data = MAGIC + six.int2byte(msg[0]) + six.int2byte(l & 0xFF) + six.int2byte(l >> 8) + m
                try:
                    self.clientSocket.sendall(data)
                except socket.error as e:
                    # Send data error
                    logger.debug('Socket connection is no more available: {}'.format(e.args))
                    self.running = False
            except Exception as e:
                logger.error('Invalid message in queue: {}'.format(e))

        logger.debug('Client processor stopped')
        try:
            self.clientSocket.close()
        except Exception:
            pass  # If can't close, nothing happens, just end thread


class ServerIPC(threading.Thread):

    def __init__(self, listenPort, clientMessageProcessor=None):
        super(self.__class__, self).__init__()
        self.port = listenPort
        self.running = False
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.threads = []
        self.clientMessageProcessor = clientMessageProcessor

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
        logger.debug('Sending message {}({}),{} to all clients'.format(msgId, REV_DICT.get(msgId), msgData))

        # Convert to bytes so length is correctly calculated
        if isinstance(msgData, six.text_type):
            msgData = msgData.encode('utf8')

        for t in self.threads:
            if t.isAlive():
                logger.debug('Sending to {}'.format(t))
                t.messages.put((msgId, msgData))

    def sendLoggofMessage(self):
        self.sendMessage(MSG_LOGOFF, '')

    def sendMessageMessage(self, message):
        self.sendMessage(MSG_MESSAGE, message)

    def sendScriptMessage(self, script):
        self.sendMessage(MSG_SCRIPT, script)

    def sendInformationMessage(self, info):
        self.sendMessage(MSG_INFORMATION, pickle.dumps(info))

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
                # Stop processing if thread is mean to stop
                if self.running is False:
                    break
                logger.debug('Got connection from {}'.format(address))

                self.cleanupFinishedThreads()  # House keeping

                logger.debug('Starting new thread, current: {}'.format(self.threads))
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
        self.messages = six.moves.queue.Queue(32)  # @UndefinedVariable

        self.connect()

    def stop(self):
        self.running = False

    def getMessage(self):
        while self.running:
            try:
                return self.messages.get(timeout=1)
            except six.moves.queue.Empty:  # @UndefinedVariable
                continue

        return None

    def sendRequestMessage(self, msg, data=None):
        logger.debug('Sending request for msg: {}({}), {}'.format(msg, REV_DICT.get(msg), data))
        if data is None:
            data = b''

        if isinstance(data, six.text_type):  # Convert to bytes if necessary
            data = data.encode('utf-8')

        l = len(data)
        msg = six.int2byte(msg) + six.int2byte(l & 0xFF) + six.int2byte(l >> 8) + data
        self.clientSocket.sendall(msg)

    def requestInformation(self):
        self.sendRequestMessage(REQ_INFORMATION)

    def sendLogin(self, username):
        self.sendRequestMessage(REQ_LOGIN, username)

    def sendLogout(self, username):
        self.sendRequestMessage(REQ_LOGOUT, username)

    def messageReceived(self):
        '''
        Override this method to automatically get notified on new message
        received. Message is at self.messages queue
        '''
        pass  # Messa

    def receiveBytes(self, number):
        msg = b''
        while self.running and len(msg) < number:
            try:
                buf = self.clientSocket.recv(number - len(msg))
                if buf == b'':
                    logger.debug('Buf {}, msg {}({})'.format(buf, msg, REV_DICT.get(msg)))
                    self.running = False
                    break
                msg += buf
            except socket.timeout:
                pass

        if self.running is False:
            logger.debug('Not running, returning None')
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
                        buf = self.clientSocket.recv(len(MAGIC) - len(msg))
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
                    except socket.timeout:  # Timeout is here so we can get stop thread
                        continue

                if self.running is False:
                    break

                # Now we get message basic data (msg + datalen)
                msg = bytearray(self.receiveBytes(3))

                # We have the magic header, here comes the message itself
                if msg is None:
                    continue

                msgId = msg[0]
                dataLen = msg[1] + (msg[2] << 8)
                if msgId not in VALID_MESSAGES:
                    raise Exception('Invalid message id: {}'.format(msgId))

                data = self.receiveBytes(dataLen)
                if data is None:
                    continue

                self.messages.put((msgId, data))
                self.messageReceived()

            except socket.error as e:
                if e.errno == errno.EINTR:
                    time.sleep(1)  #
                    continue  # Ignore interrupted system call
                logger.error('Communication with server got an error: {}'.format(toUnicode(e.strerror)))
                # self.running = False
                return
            except Exception as e:
                tb = traceback.format_exc()
                logger.error('Error: {}, trace: {}'.format(e, tb))

        try:
            self.clientSocket.close()
        except Exception:
            pass  # If can't close, nothing happens, just end thread

