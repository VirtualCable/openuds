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
import typing
import io
import string
import random

from uds_tunnel import config

TEST_CONFIG='''# Sample UDS tunnel configuration

# Pid file, optional
pidfile = {pidfile}
user = {user}

# Log level, valid are DEBUG, INFO, WARN, ERROR. Defaults to ERROR
loglevel = {loglevel}

# Log file, Defaults to stdout
logfile = {logfile}

# Max log size before rotating it. Defaults to 32 MB.
# The value is in MB. You can include or not the M string at end.
logsize = {logsize}

# Number of backup logs to keep. Defaults to 3
lognumber = {lognumber}

# Listen address. Defaults to 0.0.0.0
address = {address}

# If enforce ipv6. Defaults to False
ipv6 = {ipv6}

# Listen port. Defaults to 443
port = {port}

# Number of workers. Defaults to  0 (means "as much as cores")
workers = {workers}

# SSL Related parameters. 
ssl_certificate = {ssl_certificate}
ssl_certificate_key = {ssl_certificate_key}
ssl_password = {ssl_password}
# ssl_ciphers and ssl_dhparam are optional.
ssl_ciphers = {ssl_ciphers}
ssl_dhparam = {ssl_dhparam}

# UDS server location. https NEEDS valid certificate if https
# Must point to tunnel ticket dispatcher URL, that is under /uds/rest/tunnel/ on tunnel server
# Valid examples:
#  http://www.example.com/uds/rest/tunnel/ticket
#  https://www.example.com:14333/uds/rest/tunnel/ticket
uds_server = {uds_server}
uds_token = {uds_token}
uds_timeout = {uds_timeout}
uds_verify_ssl = {uds_verify_ssl}

# Secret to get access to admin commands (Currently only stats commands). No default for this.
# Admin commands and only allowed from "allow" ips
# So, in order to allow this commands, ensure listen address allows connections from localhost
secret = {secret}

# List of af allowed admin commands ips (Currently only stats commands).
# Only use IPs, no networks allowed
# defaults to localhost (change if listen address is different from 0.0.0.0)
allow = {allow}

# Command timeout. Command reception on tunnel will timeout after this time (in seconds)
# defaults to 3 seconds
command_timeout = {command_timeout}

use_uvloop = {use_uvloop}
'''

def get_config(**overrides) -> typing.Tuple[typing.Dict[str, typing.Any], config.ConfigurationType]:
    rand_number = random.randint(0, 100)
    values: typing.Dict[str, typing.Any] = {
        'pidfile': f'/tmp/uds_tunnel_{random.randint(0, 100)}.pid',  # Random pid file
        'user': f'user{random.randint(0, 100)}',  # Random user
        'loglevel': random.choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),  # Random log level
        'logfile': f'/tmp/uds_tunnel_{random.randint(0, 100)}.log',  # Random log file
        'logsize': random.randint(0, 100),  # Random log size
        'lognumber': random.randint(0, 100),  # Random log number
        'address': f'{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(0, 255)}',  # Random address
        'port': random.randint(0, 65535),  # Random port
        'ipv6': random.choice([True, False]),  # Random ipv6
        'workers': random.randint(1, 100),  # Random workers, 0 will return as many as cpu cores
        'ssl_certificate': f'/tmp/uds_tunnel_{rand_number}.crt',  # Random ssl certificate
        'ssl_certificate_key': f'/tmp/uds_tunnel_{rand_number}.key',  # Random ssl certificate key
        'ssl_password': f'password{random.randint(0, 100)}',  # Random ssl password
        'ssl_ciphers': f'ciphers{random.randint(0, 100)}',  # Random ssl ciphers
        'ssl_dhparam': f'/tmp/uds_tunnel_{rand_number}.dh',  # Random ssl dhparam
        'uds_server': f'https://uds_server{rand_number}/some_path',  # Random uds server
        'uds_token': f'uds_token{"".join(random.choices(string.ascii_uppercase + string.digits, k=32))}',  # Random uds token
        'uds_timeout': random.randint(0, 100),  # Random uds timeout
        'uds_verify_ssl': random.choice([True, False]),  # Random verify uds ssl
        'secret': f'secret{random.randint(0, 100)}',  # Random secret
        'allow': f'{random.randint(0, 255)}.0.0.0',  # Random allow
        'command_timeout': random.randint(0, 100),  # Random command timeout
        'use_uvloop': random.choice([True, False]),  # Random use uvloop
    }
    values.update(overrides)
    config_file = io.StringIO(TEST_CONFIG.format(**values))
    # Read it
    return  values, config.read(config_file)
