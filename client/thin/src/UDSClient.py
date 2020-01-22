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
import sys
import json

import six

from uds import ui
from uds.rest import RestRequest, RetryException
from uds.forward import forward  # pylint: disable=unused-import
from uds import VERSION
from uds.log import logger  # @UnresolvedImport
from uds import tools


# Server before this version uses "unsigned" scripts
OLD_METHOD_VERSION = '2.4.0'

def approveHost(hostName):
    from os.path import expanduser
    hostsFile = expanduser('~/.udsclient.hosts')

    try:
        with open(hostsFile, 'r') as f:
            approvedHosts = f.read().splitlines()
    except Exception:
        approvedHosts = []

    hostName = hostName.lower()

    if hostName in approvedHosts:
        return True

    errorString = 'The server {} must be approved:\n'.format(hostName)
    errorString += 'Only approve UDS servers that you trust to avoid security issues.'

    approved = ui.question("ACCESS Warning", errorString)

    if approved:
        approvedHosts.append(hostName)
        logger.debug('Host was approved, saving to approvedHosts file')
        try:
            with open(hostsFile, 'w') as f:
                f.write('\n'.join(approvedHosts))
        except Exception:
            logger.warning('Got exception writing to %s', hostsFile)

    return approved


def getWithRetry(api, url, parameters=None):
    while True:
        try:
            return api.get(url, parameters)
        except RetryException as e:
            if ui.question('Service not available', 'Error {}.\nPlease, wait a minute and press "OK" to retry, or "CANCEL" to abort'.format(e)) is True:
                continue
            raise Exception('Cancelled by user')


if __name__ == "__main__":
    logger.debug('Initializing connector')

    if six.PY3 is False:
        logger.debug('Fixing threaded execution of commands')
        import threading
        threading._DummyThread._Thread__stop = lambda x: 42  # type: ignore,  pylint:disable=protected-access

    # First parameter must be url
    try:
        uri = sys.argv[1]

        if uri == '--test':
            sys.exit(0)

        logger.debug('URI: %s', uri)
        if uri[:6] != 'uds://' and uri[:7] != 'udss://':
            raise Exception()

        ssl = uri[3] == 's'
        host, ticket, scrambler = uri.split('//')[1].split('/')
        logger.debug('ssl: %s, host:%s, ticket:%s, scrambler:%s', ssl, host, ticket, scrambler)

    except Exception:
        logger.debug('Detected execution without valid URI, exiting')
        ui.message('UDS Client', 'UDS Client Version {}'.format(VERSION))
        sys.exit(1)

    rest = RestRequest(host, ssl)
    logger.debug('Setting request URL to %s', rest.restApiUrl)

    # Main requests part
    # First, get version
    try:
        res = getWithRetry(rest, '')

        logger.debug('Got information %s', res)
        requiredVersion = res['requiredVersion']

        if requiredVersion > VERSION:
            ui.message("New UDS Client available", "A new uds version is needed in order to access this version of UDS.\nPlease, download and install it")
            sys.exit(1)

        res = getWithRetry(rest, '/{}/{}'.format(ticket, scrambler), parameters={'hostname': tools.getHostName(), 'version': VERSION})

        params = None

        if requiredVersion <= OLD_METHOD_VERSION:
            script = res.decode('base64').decode('bz2')
        else:
            # We have three elements on result:
            # * Script
            # * Signature
            # * Script data
            # We test that the Script has correct signature, and them execute it with the parameters
            script, signature, params = res['script'].decode('base64').decode('bz2'), res['signature'], json.loads(res['params'].decode('base64').decode('bz2'))
            if tools.verifySignature(script, signature) is False:
                logger.error('Signature is invalid')

                raise Exception('Invalid UDS code signature. Please, report to administrator')

        logger.debug('Script: %s', script)
        six.exec_(script, globals(), {'parent': None, 'sp':  params})
    except Exception as e:
        error = 'ERROR: {}'.format(e)
        logger.error(error)
        ui.message('Error', error)
        sys.exit(2)

    # Finalize
    try:
        tools.waitForTasks()
    except Exception:
        pass

    try:
        tools.unlinkFiles()
    except Exception:
        pass

    try:
        tools.execBeforeExit()
    except Exception:
        pass
