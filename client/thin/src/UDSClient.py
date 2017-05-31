# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
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

from uds import ui
from uds import browser
from uds.rest import RestRequest
from uds.forward import forward
from uds import VERSION
from uds.log import logger  # @UnresolvedImport
from uds import tools

import six
import sys
import webbrowser
import pickle


def approveHost(host):
    from os.path import expanduser
    hostsFile = expanduser('~/.udsclient.hosts')

    try:
        with open(hostsFile, 'r') as f:
            approvedHosts = f.read().splitlines()
    except Exception:
        approvedHosts = []

    host = host.lower()

    if host in approvedHosts:
        return True

    errorString = 'The server {} must be approved:\n'.format(host)
    errorString += 'Only approve UDS servers that you trust to avoid security issues.'

    approved = ui.question("ACCESS Warning", errorString)

    if approved:
        approvedHosts.append(host)
        logger.debug('Host was approved, saving to approvedHosts file')
        try:
            with open(hostsFile, 'w') as f:
                f.write('\n'.join(approvedHosts))
        except Exception:
            logger.warn('Got exception writing to {}'.format(hostsFile))


    return approved



if __name__ == "__main__":
    logger.debug('Initializing connector')

    if six.PY3 is False:
        logger.debug('Fixing threaded execution of commands')
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42

    # First parameter must be url
    try:
        uri = sys.argv[1]

        if uri == '--test':
            sys.exit(0)

        logger.debug('URI: {}'.format(uri))
        if uri[:6] != 'uds://' and uri[:7] != 'udss://':
            raise Exception()

        ssl = uri[3] == 's'
        host, ticket, scrambler = uri.split('//')[1].split('/')
        logger.debug('ssl: {}, host:{}, ticket:{}, scrambler:{}'.format(ssl, host, ticket, scrambler))

    except Exception:
        logger.debug('Detected execution without valid URI, exiting')
        ui.message('UDS Client', 'UDS Client Version {}'.format(VERSION))
        sys.exit(1)

    rest = RestRequest('{}://{}/rest/client'.format(['http', 'https'][ssl], host))
    logger.debug('Setting request URL to {}'.format(rest.restApiUrl))

    # Main requests part
    # First, get version
    try:
        res = rest.get('')['result']
        if res['requiredVersion'] > VERSION:
            ui.message("New UDS Client available", "A new uds version is needed in order to access this version of UDS. A browser will be openend for this download.")
            webbrowser.open(res['downloadUrl'])
            sys.exit(1)

        # Now get ticket
        res = rest.get('/{}/{}'.format(ticket, scrambler), params={'hostname': tools.getHostName(), 'version': VERSION})

    except KeyError as e:
        logger.error('Got an exception access RESULT: {}'.format(e))
    except Exception as e:
        logger.error('Got an unexpected exception: {}'.format(e))
