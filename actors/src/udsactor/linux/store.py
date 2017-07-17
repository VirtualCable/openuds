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


import six
import os

DEBUG = False

CONFIGFILE = '/etc/udsactor/udsactor.cfg' if DEBUG is False else '/tmp/udsactor.cfg'


def checkPermissions():
    return True if DEBUG else os.getuid() == 0


def readConfig():
    res = {}
    try:
        cfg = six.moves.configparser.SafeConfigParser()  # @UndefinedVariable
        cfg.optionxform = six.text_type
        cfg.read(CONFIGFILE)
        # Just reads 'uds' section
        for key in cfg.options('uds'):
            res[key] = cfg.get('uds', key)
            if res[key].lower() in ('true', 'yes', 'si'):
                res[key] = True
            elif res[key].lower() in ('false', 'no'):
                res[key] = False
    except Exception:
        pass

    return res


def writeConfig(data):
    cfg = six.moves.configparser.SafeConfigParser()  # @UndefinedVariable
    cfg.optionxform = six.text_type
    cfg.add_section('uds')
    for key, val in data.items():
        cfg.set('uds', key, str(val))

    # Ensures exists destination folder
    dirname = os.path.dirname(CONFIGFILE)
    if not os.path.exists(dirname):
        os.mkdir(dirname, mode=0o700)  # Will create only if route to path already exists, for example, /etc (that must... :-))

    with open(CONFIGFILE, 'w') as f:
        cfg.write(f)

    os.chmod(CONFIGFILE, 0o0600)

def useOldJoinSystem():
    return False

# Right now, we do not really need an application to be run on "startup" as could ocur with windows
def runApplication():
    return None

