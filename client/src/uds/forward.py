# Based on forward.py from paramiko
# Copyright (C) 2003-2007  Robey Pointer <robeypointer@gmail.com>
# https://github.com/paramiko/paramiko/blob/master/demos/forward.py

from __future__ import unicode_literals

import select
import SocketServer

import sys

import paramiko
import threading

g_verbose = True


class ForwardServer (SocketServer.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


class Handler (SocketServer.BaseRequestHandler):

    def handle(self):
        try:
            chan = self.ssh_transport.open_channel('direct-tcpip',
                                                   (self.chain_host, self.chain_port),
                                                   self.request.getpeername())
        except Exception as e:
            verbose('Incoming request to %s:%d failed: %s' % (self.chain_host,
                                                              self.chain_port,
                                                              repr(e)))
            return
        if chan is None:
            verbose('Incoming request to %s:%d was rejected by the SSH server.' %
                    (self.chain_host, self.chain_port))
            return

        verbose('Connected!  Tunnel open %r -> %r -> %r' % (self.request.getpeername(),
                                                            chan.getpeername(), (self.chain_host, self.chain_port)))
        while self.event.is_set() is False:
            r, w, x = select.select([self.request, chan], [], [], 1)

            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)

        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        verbose('Tunnel closed from %r' % (peername,))


def verbose(s):
    if g_verbose:
        print(s)


class ForwardThread(threading.Thread):
    def __init__(self, server, port, username, password, localPort, redirectHost, redirectPort):
        threading.Thread.__init__(self)
        self.client = None
        self.fs = None

        self.server = server
        self.port = int(port)
        self.username = username
        self.password = password

        self.localPort = int(localPort)
        self.redirectHost = redirectHost
        self.redirectPort = redirectPort

        self.stopEvent = threading.Event()

    def run(self):
        self.client = paramiko.SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        verbose('Connecting to ssh host %s:%d ...' % (self.server, self.port))

        self.client.connect(self.server, self.port, username=self.username, password=self.password)

        class SubHander (Handler):
            chain_host = self.redirectHost
            chain_port = self.redirectPort
            ssh_transport = self.client.get_transport()
            event = self.stopEvent

        self.fs = ForwardServer(('', self.redirectPort), SubHander)
        self.fs.serve_forever()

    def stop(self):
        try:
            self.stopEvent.set()
            self.fs.shutdown()

            if self.client is not None:
                self.client.close()
        except Exception:
            pass


def forward(server, port, username, password, localPort, redirectHost, redirectPort):
    port, redirectPort = int(port), int(redirectPort)


    verbose('Connected')

    ft = ForwardThread(server, port, username, password, localPort, redirectHost, redirectPort)

    ft.start()

    return ft
