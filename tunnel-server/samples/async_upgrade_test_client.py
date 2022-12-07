#!/usr/bin/env python3

import socket
import ssl
import logging
import socket
import typing


logger = logging.getLogger(__name__)



def main():
    # Init logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    context = ssl.create_default_context()

    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    # Open socket to localhost port 7777, TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(66.0)
        sock.connect(('127.0.0.1', 7777))
        sock.sendall(b'ABCD')
        # Upgrade to ssl
        ssl_sock = context.wrap_socket(sock, server_side=False)
        # Write test OPEN, split on 2 sends
        ssl_sock.sendall(b'OPEN')
        ssl_sock.sendall(b'X'*48)
        # Read response
        while True:
            data = ssl_sock.recv(16384)
            if not data:
                break
            print(data)


    
if __name__ == '__main__':
    main()

