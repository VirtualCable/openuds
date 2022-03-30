#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2021-2022 Virtual Cable S.L.U.
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
import os
import pwd
import sys
import asyncio
import argparse
import signal
import ssl
import socket
import logging
import threading
import typing

import setproctitle


from uds_tunnel import config, proxy, consts, processes, stats

if typing.TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.managers import Namespace

BACKLOG = 1024

logger = logging.getLogger(__name__)

do_stop = False


def stop_signal(signum, frame):
    global do_stop
    do_stop = True
    logger.debug('SIGNAL %s, frame: %s', signum, frame)


def setup_log(cfg: config.ConfigurationType) -> None:
    from logging.handlers import RotatingFileHandler

    # Update logging if needed
    if cfg.log_file:
        fileh = RotatingFileHandler(
            filename=cfg.log_file,
            mode='a',
            maxBytes=cfg.log_size,
            backupCount=cfg.log_number,
        )
        formatter = logging.Formatter(consts.LOGFORMAT)
        fileh.setFormatter(formatter)
        log = logging.getLogger()
        log.setLevel(cfg.log_level)
        # for hdlr in log.handlers[:]:
        #     log.removeHandler(hdlr)
        log.addHandler(fileh)
    else:
        # Setup basic logging
        log = logging.getLogger()
        log.setLevel(cfg.log_level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(cfg.log_level)
        formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )  # Basic log format, nice for syslog
        handler.setFormatter(formatter)
        log.addHandler(handler)


async def tunnel_proc_async(
    pipe: 'Connection', cfg: config.ConfigurationType, ns: 'Namespace'
) -> None:

    loop = asyncio.get_event_loop()

    tasks: typing.List[asyncio.Task] = []

    def get_socket() -> typing.Optional[socket.socket]:
        try:
            while True:
                # Clear back event, for next data
                msg: typing.Optional[
                    typing.Tuple[socket.socket, typing.Tuple[str, int]]
                ] = pipe.recv()
                if msg:
                    return msg[0]
        except Exception:
            logger.exception('Receiving data from parent process')
            return None

    async def run_server() -> None:
        # Instantiate a proxy redirector for this process (we only need one per process!!)
        tunneler = proxy.Proxy(cfg, ns)

        # Generate SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cfg.ssl_certificate, cfg.ssl_certificate_key)

        if cfg.ssl_ciphers:
            context.set_ciphers(cfg.ssl_ciphers)

        if cfg.ssl_dhparam:
            context.load_dh_params(cfg.ssl_dhparam)

        async def processSocket(ssock: socket.socket) -> None:
            sock = curio.io.Socket(ssock)
            try:
                # First, ensure handshake (simple handshake) and command
                async with curio.timeout_after(3):  # type: ignore
                    data = await sock.recv(len(consts.HANDSHAKE_V1))

                if data != consts.HANDSHAKE_V1:
                    raise Exception(data)  # Invalid handshake
            except (curio.errors.CancelledError, Exception) as e:
                logger.error('HANDSHAKE from %s (%s)', address, 'timeout' if isinstance(e, curio.errors.CancelledError) else e)
                # Close Source and continue
                await sock.close()
                return
            sslsock = await context.wrap_socket(
                sock, server_side=True  # type: ignore
            )
            await group.spawn(tunneler, sslsock, address)
            del sslsock


        while True:
            address: typing.Tuple[str, int] = ('', 0)
            try:
                sock = await loop.run_in_executor(None, get_socket)
                if not sock:
                    break  # No more sockets, exit
                logger.debug(f'CONNECTION from {address!r} (pid: {os.getpid()})')
                tasks.append(asyncio.create_task(tunneler(sock, context)))
            except Exception:
                logger.error('NEGOTIATION ERROR from %s', address[0])

    # create task for server
    tasks.append(asyncio.create_task(run_server()))

    while tasks:
        tasks_number = len(tasks)
        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)
        # Remove finished tasks from list
        del tasks[:tasks_number]


def process_connection(
    client: socket.socket, addr: typing.Tuple[str, str], conn: 'Connection'
) -> None:
    data: bytes = b''
    try:
        # First, ensure handshake (simple handshake) and command
        data = client.recv(len(consts.HANDSHAKE_V1))

        if data != consts.HANDSHAKE_V1:
            raise Exception()  # Invalid handshake
        conn.send((client, addr))
        del client  # Ensure socket is controlled on child process
    except Exception:
        logger.error('HANDSHAKE invalid from %s (%s)', addr, data.hex())
        # Close Source and continue
        client.close()

    logger.info('PROCESS %s stopped', os.getpid())


def tunnel_main():
    cfg = config.read()

    # Try to bind to port as running user
    # Wait for socket incoming connections and spread them
    socket.setdefaulttimeout(
        3.0
    )  # So we can check for stop from time to time and not block forever
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    # We will not reuse port, we only want a UDS tunnel server running on a port
    # but this may change on future...
    # try:
    #     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    # except (AttributeError, OSError) as e:
    #     logger.warning('socket.REUSEPORT not available')
    try:
        sock.bind((cfg.listen_address, cfg.listen_port))
        sock.listen(BACKLOG)

        # If running as root, and requested drop privileges after port bind
        if os.getuid() == 0 and cfg.user:
            logger.debug('Changing to  user %s', cfg.user)
            pwu = pwd.getpwnam(cfg.user)
            # os.setgid(pwu.pw_gid)
            os.setuid(pwu.pw_uid)

        setup_log(cfg)

        logger.info(
            'Starting tunnel server on %s:%s', cfg.listen_address, cfg.listen_port
        )
        setproctitle.setproctitle(f'UDSTunnel {cfg.listen_address}:{cfg.listen_port}')

        # Create pid file
        if cfg.pidfile:
            with open(cfg.pidfile, mode='w') as f:
                f.write(str(os.getpid()))

    except Exception as e:
        sys.stderr.write(f'Tunnel startup error: {e}\n')
        logger.error('MAIN: %s', e)
        return

    # Setup signal handlers
    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)

    stats_collector = stats.GlobalStats()

    prcs = processes.Processes(tunnel_proc_async, cfg, stats_collector.ns)

    try:
        while not do_stop:
            try:
                client, addr = sock.accept()
                logger.info('CONNECTION from %s', addr)

                # Check if we have reached the max number of connections
                # First part is checked on a thread, if HANDSHAKE is valid
                # we will send socket to process pool
                threading.Thread(
                    target=process_connection, args=(client, addr, prcs.best_child())
                ).start()
            except socket.timeout:
                pass  # Continue and retry
            except Exception as e:
                logger.error('LOOP: %s', e)
    except Exception as e:
        sys.stderr.write(f'Error: {e}\n')
        logger.error('MAIN: %s', e)

    if sock:
        sock.close()

    prcs.stop()

    try:
        if cfg.pidfile:
            os.unlink(cfg.pidfile)
    except Exception:
        pass

    logger.info('FINISHED')


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-t', '--tunnel', help='Starts the tunnel server', action='store_true'
    )
    group.add_argument('-r', '--rdp', help='RDP Tunnel for traffic accounting')
    group.add_argument(
        '-s',
        '--stats',
        help='get current global stats from RUNNING tunnel',
        action='store_true',
    )
    group.add_argument(
        '-d',
        '--detailed-stats',
        help='get current detailed stats from RUNNING tunnel',
        action='store_true',
    )
    args = parser.parse_args()

    if args.tunnel:
        tunnel_main()
    elif args.rdp:
        pass
    elif args.detailed_stats:
        asyncio.run(stats.getServerStats(True))
    elif args.stats:
        asyncio.run(stats.getServerStats(False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
