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
from __future__ import unicode_literals

from django.utils.translation import ugettext as _

from uds.core.util import Config
from uds.core.util.State import State
from uds.core.util import log
from uds.core.managers import cryptoManager
from uds.REST import Handler, AccessDenied, RequestError
from uds.models import UserService


import datetime

import logging

logger = logging.getLogger(__name__)


# Actor key, configurable in Security Section of administration interface
actorKey = Config.Config.section(Config.SECURITY_SECTION).value('actorKey',
                                                                cryptoManager().uuid(datetime.datetime.now()).replace('-', ''),
                                                                type=Config.Config.NUMERIC_FIELD)
actorKey.get()


# Enclosed methods under /actor path
class Actor(Handler):
    '''
    Processes actor requests
    '''
    authenticated = False  # Actor requests are not authenticated

    def test(self):
        return {'result': _('Correct'), 'date': datetime.datetime.now()}

    def getClientIdAndMessage(self):

        # Now we will process .../clientIds/message
        if len(self._args) < 3:
            raise RequestError('Invalid arguments provided')

        clientIds, message = self._args[1].split(',')[:5], self._args[2]

        return clientIds, message

    def validateRequest(self):
        # Ensures that key is first parameter
        # Here, path will be .../actor/KEY/... (probably /rest/actor/KEY/...)
        if self._args[0] != actorKey.get(True):
            raise AccessDenied('Invalid actor key')

    def processRequest(self, clientIds, message, data):
        logger.debug("Called message for id_ {0}, message \"{1}\" and data \"{2}\"".format(clientIds, message, data))
        res = ""
        try:
            services = UserService.objects.filter(unique_id__in=clientIds, state__in=[State.USABLE, State.PREPARING])
            if services.count() == 0:
                res = ""
            else:
                inUse = services[0].in_use
                res = services[0].getInstance().osmanager().process(services[0], message, data)
                services = UserService.objects.filter(unique_id__in=clientIds, state__in=[State.USABLE, State.PREPARING])
                if services.count() > 0 and services[0].in_use != inUse:  # If state changed, log it
                    type_ = inUse and 'login' or 'logout'
                    uniqueId = services[0].unique_id
                    serviceIp = ''
                    username = ''
                    log.useLog(type_, uniqueId, serviceIp, username)
        except Exception as e:
            logger.error("Exception at message (client): {0}".format(e))
            res = ""
        logger.debug("Returning {0}".format(res))
        return res

    def get(self):
        '''
        Processes get requests
        '''
        logger.debug("Actor args for GET: {0}".format(self._args))

        self.validateRequest()  # Wil raise an access denied exception if not valid

        # if path is .../test (/rest/actor/KEY/test)
        if self._args[1] == 'test':
            return self.test()

        clientIds, message = self.getClientIdAndMessage()

        try:
            data = self._args[3]
        except Exception:
            data = ''

        return self.processRequest(clientIds, message, data)

    def post(self):
        '''
        Processes post requests
        '''
        self.validateRequest()  # Wil raise an access denied exception if not valid

        clientIds, message = self.getClientIdAndMessage()

        data = self._params[0]

        return self.processRequest(clientIds, message, data)
