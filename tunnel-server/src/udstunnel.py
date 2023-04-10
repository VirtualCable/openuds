#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
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
from concurrent.futures import ThreadPoolExecutor
# event for stop notification
import threading
import typing

try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass  # no uvloop support

try:
    import setproctitle
except ImportError:
    setproctitle = None  # type: ignore


from uds_tunnel import config, proxy, consts, processes, stats

if typing.TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.managers import Namespace


logger = logging.getLogger(__name__)

do_stop: threading.Event = threading.Event()


def stop_signal(signum: int, frame: typing.Any) -> None:
    do_stop.set()
    logger.debug('SIGNAL %s, frame: %s', signum, frame)


def setup_log(cfg: config.ConfigurationType) -> None:
    from logging.handlers import RotatingFileHandler

    # Update logging if needed
    if cfg.logfile:
        fileh = RotatingFileHandler(
            filename=cfg.logfile,
            mode='a',
            maxBytes=cfg.logsize,
            backupCount=cfg.lognumber,
        )
        formatter = logging.Formatter(consts.LOGFORMAT)
        fileh.setFormatter(formatter)
        log = logging.getLogger()
        log.setLevel(cfg.loglevel)
        # for hdlr in log.handlers[:]:
        #     log.removeHandler(hdlr)
        log.addHandler(fileh)
    else:
        # Setup basic logging
        log = logging.getLogger()
        log.setLevel(cfg.loglevel)
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(cfg.loglevel)
        formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )  # Basic log format, nice for syslog
        handler.setFormatter(formatter)
        log.addHandler(handler)

    # If debug, print config
    if cfg.loglevel.lower() == 'debug':
        logger.debug('Configuration: %s', cfg)


async def tunnel_proc_async(
    pipe: 'Connection', cfg: config.ConfigurationType, ns: 'Namespace'
) -> None:
    
    loop = asyncio.get_running_loop()

    tasks: typing.List[asyncio.Task] = []

    def add_autoremovable_task(task: asyncio.Task) -> None:
        tasks.append(task)
        task.add_done_callback(tasks.remove)

    def get_socket() -> typing.Tuple[typing.Optional[socket.socket], typing.Optional[typing.Tuple[str, int]]]:
        try:
            while True:
                # Clear back event, for next data
                msg: typing.Optional[
                    typing.Tuple[socket.socket, typing.Tuple[str, int]]
                ] = pipe.recv()
                if msg:
                    return msg
        except EOFError:
            logger.debug('Parent process closed connection')
            pipe.close()
            return None, None
        except Exception:
            logger.exception('Receiving data from parent process')
            pipe.close()
            return None, None

    async def run_server() -> None:
        # Generate SSL context
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        args: typing.Dict[str, typing.Any] = {
            'certfile': cfg.ssl_certificate,
        }
        if cfg.ssl_certificate_key:
            args['keyfile'] = cfg.ssl_certificate_key
        if cfg.ssl_password:
            args['password'] = cfg.ssl_password
        
        context.load_cert_chain(**args)

        # Set min version from string (1.2 or 1.3) as ssl.TLSVersion.TLSv1_2 or ssl.TLSVersion.TLSv1_3
        if cfg.ssl_min_tls_version in ('1.2', '1.3'):
            context.minimum_version = getattr(ssl.TLSVersion, f'TLSv1_{cfg.ssl_min_tls_version.split(".")[1]}')
        # Any other value will be ignored

        if cfg.ssl_ciphers:
            context.set_ciphers(cfg.ssl_ciphers)

        if cfg.ssl_dhparam:
            context.load_dh_params(cfg.ssl_dhparam)

        try:
            while True:
                address: typing.Optional[typing.Tuple[str, int]] = ('', 0)
                try:
                    (sock, address) = await loop.run_in_executor(None, get_socket)
                    if not sock:
                        break  # No more sockets, exit
                    logger.debug(f'CONNECTION from {address!r} (pid: {os.getpid()})')
                    # Due to proxy contains an "event" to stop, we need to create a new one for each connection
                    add_autoremovable_task(asyncio.create_task(proxy.Proxy(cfg, ns)(sock, context)))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error('NEGOTIATION ERROR from %s', address[0] if address else 'unknown')
        except asyncio.CancelledError:
            pass  # Stop

    # create task for server
    
    add_autoremovable_task(asyncio.create_task(run_server()))

    try:
        while tasks and not do_stop.is_set():
            to_wait = tasks[:]  # Get a copy of the list
            # Wait for "to_wait" tasks to finish, stop every 2 seconds to check if we need to stop
            done, _ = await asyncio.wait(to_wait, return_when=asyncio.FIRST_COMPLETED, timeout=2)
    except asyncio.CancelledError:
        logger.info('Task cancelled')
        do_stop.set()  # ensure we stop

    logger.debug('Out of loop, stopping tasks: %s, running: %s', tasks, do_stop.is_set())

    # If any task is still running, cancel it
    for task in tasks:
        try:
            task.cancel()
        except asyncio.CancelledError:
            pass  # Ignore, we are stopping
    
    # for task in tasks:
    #    task.cancel()

    # Wait for all tasks to finish
    await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    logger.info('PROCESS %s stopped', os.getpid())

def process_connection(
    client: socket.socket, addr: typing.Tuple[str, str], conn: 'Connection'
) -> None:
    data: bytes = b''
    try:
        # First, ensure handshake (simple handshake) and command
        data = client.recv(len(consts.HANDSHAKE_V1))

        if data != consts.HANDSHAKE_V1:
            raise Exception('Invalid data from {}: {}'.format(addr[0], data.hex()))  # Invalid handshake
        conn.send((client, addr))
        del client  # Ensure socket is controlled on child process
    except Exception as e:
        logger.error('HANDSHAKE invalid from %s: %s', addr[0], e)
        # Close Source and continue
        client.close()


def tunnel_main(args: 'argparse.Namespace') -> None:
    cfg = config.read(args.config)

    # Try to bind to port as running user
    # Wait for socket incoming connections and spread them
    socket.setdefaulttimeout(
        3.0
    )  # So we can check for stop from time to time and not block forever
    af_inet = socket.AF_INET6 if args.ipv6 or cfg.ipv6 or ':' in cfg.listen_address else socket.AF_INET
    sock = socket.socket(af_inet, socket.SOCK_STREAM)
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
        sock.listen(consts.BACKLOG)

        # If running as root, and requested drop privileges after port bind
        if os.getuid() == 0 and cfg.user:
            logger.debug('Changing to user %s', cfg.user)
            pwu = pwd.getpwnam(cfg.user)
            # os.setgid(pwu.pw_gid)
            os.setuid(pwu.pw_uid)

        setup_log(cfg)

        logger.info(
            'Starting tunnel server on %s:%s', cfg.listen_address, cfg.listen_port
        )
        if setproctitle:
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
    try:
        signal.signal(signal.SIGINT, stop_signal)
        signal.signal(signal.SIGTERM, stop_signal)
    except Exception as e:
        # Signal not available on threads, and we use threads on tests, 
        # so we will ignore this because on tests signals are not important
        logger.warning('Signal not available: %s', e)

    stats_collector = stats.GlobalStats()

    prcs = processes.Processes(tunnel_proc_async, cfg, stats_collector.ns)

    with ThreadPoolExecutor(max_workers=16) as executor:
        try:
            while not do_stop.is_set():
                try:
                    client, addr = sock.accept()
                    # logger.info('CONNECTION from %s', addr)

                    # Check if we have reached the max number of connections
                    # First part is checked on a thread, if HANDSHAKE is valid
                    # we will send socket to process pool
                    # Note: We use a thread pool here because we want to
                    #       ensure no denial of service is possible, or at least
                    #       we try to limit it (if connection delays too long, we will close it on the thread)
                    executor.submit(process_connection, client, addr, prcs.best_child())
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
    # group.add_argument('-r', '--rdp', help='RDP Tunnel for traffic accounting')
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
    # Config file
    parser.add_argument(
        '-c',
        '--config',
        help=f'Config file to use (default: {consts.CONFIGFILE})',
        default=consts.CONFIGFILE,
    )
    # If force ipv6
    parser.add_argument(
        '-6',
        '--ipv6',
        help='Force IPv6 for tunnel server',
        action='store_true',
    )
    args = parser.parse_args()

    if args.tunnel:
        tunnel_main(args)
    elif args.detailed_stats:
        asyncio.run(stats.getServerStats(True))
    elif args.stats:
        asyncio.run(stats.getServerStats(False))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
