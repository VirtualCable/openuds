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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
# pyright: reportUnknownMemberType=false
import typing
import os
import os.path
import logging
import configparser

logger = logging.getLogger(__name__)

# VARS is {SECTION: {VARIABLE: VALUE}}
config: configparser.ConfigParser = configparser.ConfigParser()

VAR_FILE: typing.Final[str] = 'test-vars.ini'


def load() -> None:
    if config.sections():
        return

    try:
        # If exists on current folder, use it
        if os.path.exists(VAR_FILE):
            config.read(VAR_FILE)
        # if exists on parent folder, use it
        elif os.path.exists(os.path.join('..', VAR_FILE)):
            config.read(os.path.join('..', VAR_FILE))
    except configparser.Error:
        pass  # Ignore errors, no vars will be loaded


def get_vars(section: str) -> typing.Dict[str, str]:
    load()  # Ensure vars are loaded

    try:
        v = dict(config[section])
        if v.get('enabled', 'false') == 'false':
            logger.info('Section %s is disabled (use enabled=true to enable it on %s file)', section, VAR_FILE)
            return {}  # If section is disabled, return empty dict
        return v
    except KeyError:
        return {}
