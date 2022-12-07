#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from socket import socket
import ssl
import typing
from multiprocessing import Process, Queue


def handle(q: 'Queue[socket]'):
    qsock = q.get()
    context = ssl.create_default_context()

    ssock = context.wrap_socket(qsock, server_hostname='httpbin.org')
    ssock.send(b'GET /get\r\n')
    print('rest:', ssock.recv(10048))

if __name__ == '__main__':
    sock = socket()
    sock.connect(('httpbin.org', 443))

    q: 'Queue[socket]' = Queue()
    proc = Process(target=handle, args=(q,))
    proc.start()
    # use the function from above to serialize socket
    q.put(sock)
    proc.join()