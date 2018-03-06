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
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _, ugettext_lazy
from django.conf import settings
from uds.core.services import types as serviceTypes
from uds.core.ui.UserInterface import gui
from uds.core import osmanagers
from uds.core.util.State import State
from uds.core.util import log
import six

import logging
from uds.core.managers.UserServiceManager import UserServiceManager

logger = logging.getLogger(__name__)


class LinuxOsManager(osmanagers.OSManager):
    typeName = _('Linux OS Manager')
    typeType = 'LinuxManager'
    typeDescription = _('Os Manager to control linux virtual machines')
    iconFile = 'losmanager.png'

    servicesType = (serviceTypes.VDI,)

    onLogout = gui.ChoiceField(
        label=_('Logout Action'),
        order=10,
        rdonly=True,
        tooltip=_('What to do when user logs out from service'),
        values=[
            {'id': 'keep', 'text': ugettext_lazy('Keep service assigned')},
            {'id': 'remove', 'text': ugettext_lazy('Remove service')},
            {'id': 'keep-always', 'text': ugettext_lazy('Keep service assigned even on new publication')},
        ],
        defvalue='keep')

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        defvalue=-1,
        rdonly=False, order=11,
        tooltip=_('Maximum idle time (in seconds) before session is automatically closed to the user (<= 0 means no max idle time).'),
        required=True)

    def __setProcessUnusedMachines(self):
        self.processUnusedMachines = self._onLogout == 'remove'

    def __init__(self, environment, values):
        super(LinuxOsManager, self).__init__(environment, values)
        if values is not None:
            self._onLogout = values['onLogout']
            self._idle = int(values['idle'])
        else:
            self._onLogout = ''
            self._idle = -1

        self.__setProcessUnusedMachines()

    def release(self, service):
        pass

    def getName(self, service):
        '''
        gets name from deployed
        '''
        return service.getName()

    def infoVal(self, service):
        return 'rename:' + self.getName(service)

    def infoValue(self, service):
        return 'rename\r' + self.getName(service)

    def notifyIp(self, uid, service, data):
        si = service.getInstance()

        ip = ''
        # Notifies IP to deployed
        pairs = data.split(',')
        for p in pairs:
            key, val = p.split('=')
            if key.lower() == uid.lower():
                si.setIp(val)
                ip = val
                break

        self.logKnownIp(service, ip)
        service.updateData(si)

    def doLog(self, service, data, origin=log.OSMANAGER):
        # Stores a log associated with this service
        try:
            msg, level = data.split('\t')
            try:
                level = int(level)
            except Exception:
                logger.debug('Do not understand level {}'.format(level))
                level = log.INFO
            log.doLog(service, level, msg, origin)
        except Exception:
            log.doLog(service, log.ERROR, "do not understand {0}".format(data), origin)

    def process(self, userService, msg, data, options):
        '''
        We understand this messages:
        * msg = info, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class), old method
        * msg = information, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class), new method
        * msg = logon, data = Username, Informs that the username has logged in inside the machine
        * msg = logoff, data = Username, Informs that the username has logged out of the machine
        * msg = ready, data = None, Informs machine ready to be used
        '''
        logger.info("Invoked LinuxOsManager for {0} with params: {1},{2}".format(userService, msg, data))
        # We get from storage the name for this userService. If no name, we try to assign a new one
        ret = "ok"
        notifyReady = False
        doRemove = False
        state = userService.os_state

        # Old "info" state, will be removed in a near future
        if msg == "info":
            ret = self.infoVal(userService)
            state = State.PREPARING
        elif msg == "information":
            ret = self.infoValue(userService)
            state = State.PREPARING
        elif msg == "log":
            self.doLog(userService, data, log.ACTOR)
        elif msg == "login":
            self.loggedIn(userService, data, False)
            ip, hostname = userService.getConnectionSource()
            deadLine = userService.deployed_service.getDeadline()
            ret = "{0}\t{1}\t{2}".format(ip, hostname, 0 if deadLine is None else deadLine)
        elif msg == "logout":
            self.loggedOut(userService, data, False)
            if userService.in_use == False and self._onLogout == 'remove':
                doRemove = True
        elif msg == "ip":
            # This ocurss on main loop inside machine, so userService is usable
            state = State.USABLE
            self.notifyIp(userService.unique_id, userService, data)
        elif msg == "ready":
            self.toReady(userService)
            state = State.USABLE
            notifyReady = True
            self.notifyIp(userService.unique_id, userService, data)

        userService.setOsState(state)

        # If notifyReady is not true, save state, let UserServiceManager do it for us else
        if doRemove is True:
            userService.release()
        else:
            if notifyReady is False:
                userService.save()
            else:
                UserServiceManager.manager().notifyReadyFromOsManager(userService, '')
        logger.debug('Returning {0}'.format(ret))
        return ret

    def processUnused(self, userService):
        '''
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        '''
        if self._onLogout == 'remove':
            userService.remove()

    def isPersistent(self):
        return not self._onLogout == 'keep-always'

    def checkState(self, service):
        logger.debug('Checking state for service {0}'.format(service))
        return State.RUNNING

    def maxIdle(self):
        '''
        On production environments, will return no idle for non removable machines
        '''
        if self._idle <= 0:  # or (settings.DEBUG is False and self._onLogout != 'remove'):
            return None

        return self._idle

    def marshal(self):
        '''
        Serializes the os manager data so we can store it in database
        '''
        return '\t'.join(['v2', self._onLogout, six.text_type(self._idle)])

    def unmarshal(self, s):
        data = s.split('\t')
        if data[0] == 'v1':
            self._onLogout = data[1]
            self._idle = -1
        elif data[0] == 'v2':
            self._onLogout, self._idle = data[1], int(data[2])

        self.__setProcessUnusedMachines()

    def valuesDict(self):
        return {'onLogout': self._onLogout, 'idle': self._idle}
