# -*- coding: utf-8 -*-
#
# Copyright (c) 2020 Virtual Cable S.L.U.
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
import hashlib
import multiprocessing
import configparser
import logging
import typing

from .consts import CONFIGFILE

logger = logging.getLogger(__name__)

class ConfigurationType(typing.NamedTuple):
    log_level: str
    log_file: str

    listen_address: str
    listen_port: int

    workers: int
    
    ssl_certificate: str
    ssl_certificate_key: str
    ssl_ciphers: str
    ssl_dhparam: str

    uds_server: str

    secret: str
    allow: typing.Set[str]
    
    storage: str


def read() -> ConfigurationType:
    with open(CONFIGFILE, 'r') as f:
        config_str = '[uds]\n' + f.read()

    cfg = configparser.ConfigParser()
    cfg.read_string(config_str)

    uds = cfg['uds']

    h = hashlib.sha256()
    h.update(uds.get('secret', '').encode())
    secret = h.hexdigest()

    try:
        return ConfigurationType(
            log_level=uds.get('loglevel', 'ERROR'),
            log_file=uds.get('logfile', ''),
            listen_address=uds.get('address', '0.0.0.0'),
            listen_port=int(uds.get('port', '443')),
            workers=int(uds.get('workers', '0')) or multiprocessing.cpu_count(),
            ssl_certificate=uds['ssl_certificate'],
            ssl_certificate_key=uds['ssl_certificate_key'],
            ssl_ciphers=uds.get('ssl_ciphers'),
            ssl_dhparam=uds.get('ssl_dhparam'),
            uds_server=uds['uds_server'],
            secret=secret,
            allow=set(uds.get('allow', '127.0.0.1').split(',')),
            storage=uds['storage']
        )
    except ValueError as e:
        raise Exception(f'Mandatory configuration file in incorrect format: {e.args[0]}. Please, revise  {CONFIGFILE}')
    except KeyError as e:
        raise Exception(f'Mandatory configuration parameter not found: {e.args[0]}. Please, revise {CONFIGFILE}')
