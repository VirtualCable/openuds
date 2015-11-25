# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

from django.utils.translation import ugettext_lazy as _
from uds.core import services
from uds.core.util.State import State
from uds.core.util.AutoAttributes import AutoAttributes
import logging

logger = logging.getLogger(__name__)


class IPMachineDeployed(AutoAttributes, services.UserDeployment):
    suggestedTime = 10

    def __init__(self, environment, **kwargs):
        AutoAttributes.__init__(self, ip=str, reason=str, state=str)
        services.UserDeployment.__init__(self, environment, **kwargs)
        self._state = State.FINISHED

    def setIp(self, ip):
        logger.debug('Setting IP to %s (ignored)' % ip)

    def getIp(self):
        return self._ip.split('~')[0]

    def getName(self):
        return _("IP ") + self._ip.replace('~', ':')

    def getUniqueId(self):
        return self._ip.replace('~', ':')

    def setReady(self):
        self._state = State.FINISHED
        return self._state

    def __deploy(self):
        ip = self.service().getUnassignedMachine()
        if ip is None:
            self._reason = 'No machines left'
            self._state = State.ERROR
        else:
            self._ip = ip
            self._state = State.FINISHED
        self.dbservice().setInUse(True)
        self.dbservice().save()
        return self._state

    def deployForUser(self, user):
        logger.debug("Starting deploy of {0} for user {1}".format(self._ip, user))
        return self.__deploy()

    def checkState(self):
        return self._state

    def finish(self):
        pass

    def reasonOfError(self):
        '''
        If a publication produces an error, here we must notify the reason why it happened. This will be called just after
        publish or checkPublishingState if they return State.ERROR
        '''
        return self._reason

    def cancel(self):
        return self.destroy()

    def destroy(self):
        if self._ip != '':
            self.service().unassignMachine(self._ip)
        self._state = State.FINISHED
        return self._state
