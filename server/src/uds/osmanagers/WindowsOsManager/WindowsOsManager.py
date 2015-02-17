# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
# All rights reserved.
#

'''
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from django.conf import settings
from uds.core.ui.UserInterface import gui
from uds.core import osmanagers
from uds.core.managers.UserServiceManager import UserServiceManager
from uds.core.util.State import State
from uds.core.util import log
import six

import logging

logger = logging.getLogger(__name__)


def scrambleMsg(data):
    '''
    Simple scrambler so password are not seen at source page
    '''
    if isinstance(data, six.text_type):
        data = data.encode('utf8')
    res = []
    n = 0x32
    for c in data[::-1]:
        res.append(chr(ord(c) ^ n))
        n = (n + ord(c)) & 0xFF
    return six.text_type(b''.join(res).encode('hex'))


class WindowsOsManager(osmanagers.OSManager):
    typeName = _('Windows Basic OS Manager')
    typeType = 'WindowsManager'
    typeDescription = _('Os Manager to control windows machines without domain. (Basically renames machine)')
    iconFile = 'wosmanager.png'

    onLogout = gui.ChoiceField(
        label=_('On Logout'),
        order=10,
        rdonly=True,
        tooltip=_('What to do when user logs out from service'),
        values=[
            {'id': 'keep', 'text': _('Keep service assigned')},
            {'id': 'remove', 'text': _('Remove service')}
        ],
        defvalue='keep'
    )

    idle = gui.NumericField(
        label=_("Max.Idle time"),
        length=4,
        defvalue=-1,
        rdonly=False,
        order=11,
        tooltip=_('Maximum idle time (in seconds) before session is automaticatlly closed to the user (<= 0 means no max. idle time)'),
        required=True
)

    @staticmethod
    def validateLen(length):
        try:
            length = int(length)
        except Exception:
            raise osmanagers.OSManager.ValidationException(_('Length must be numeric!!'))
        if length > 6 or length < 1:
            raise osmanagers.OSManager.ValidationException(_('Length must be betwen 1 and 6'))
        return length

    def __setProcessUnusedMachines(self):
        self.processUnusedMachines = self._onLogout == 'remove'

    def __init__(self, environment, values):
        super(WindowsOsManager, self).__init__(environment, values)
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
            logger.exception('LinuxOs Manager message log: ')
            log.doLog(service, log.ERROR, "do not understand {0}".format(data), origin)

    def process(self, service, msg, data, options):
        '''
        We understand this messages:
        * msg = info, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (old method)
        * msg = information, data = None. Get information about name of machine (or domain, in derived WinDomainOsManager class) (new method)
        * msg = logon, data = Username, Informs that the username has logged in inside the machine
        * msg = logoff, data = Username, Informs that the username has logged out of the machine
        * msg = ready, data = None, Informs machine ready to be used
        '''
        logger.info("Invoked WindowsOsManager for {0} with params: {1},{2}".format(service, msg, data))
        # We get from storage the name for this service. If no name, we try to assign a new one
        ret = "ok"
        notifyReady = False
        doRemove = False
        state = service.os_state
        if msg == "info":
            ret = self.infoVal(service)
            state = State.PREPARING
        elif msg == "information":
            ret = self.infoValue(service)
            state = State.PREPARING
        elif msg == "log":
            self.doLog(service, data, log.ACTOR)
        elif msg == "logon" or msg == 'login':
            if '\\' not in data:
                self.loggedIn(service, data, False)
            service.setInUse(True)
            # We get the service logged hostname & ip and returns this
            ip, hostname = service.getConnectionSource()
            ret = "{0}\t{1}".format(ip, hostname)
        elif msg == "logoff" or msg == 'logout':
            self.loggedOut(service, data, False)
            if self._onLogout == 'remove':
                doRemove = True
        elif msg == "ip":
            # This ocurss on main loop inside machine, so service is usable
            state = State.USABLE
            self.notifyIp(service.unique_id, service, data)
        elif msg == "ready":
            state = State.USABLE
            notifyReady = True
            self.notifyIp(service.unique_id, service, data)

        service.setOsState(state)

        # If notifyReady is not true, save state, let UserServiceManager do it for us else
        if doRemove is True:
            service.remove()
        else:
            if notifyReady is False:
                service.save()
            else:
                logger.debug('Notifying ready')
                UserServiceManager.manager().notifyReadyFromOsManager(service, '')
        logger.debug('Returning {} to {} message'.format(ret, msg))
        if options is not None and options.get('scramble', True) is False:
            return ret
        return scrambleMsg(ret)

    def processUnused(self, userService):
        '''
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        '''
        if self._onLogout == 'remove':
            userService.remove()

    def checkState(self, service):
        logger.debug('Checking state for service {0}'.format(service))
        return State.RUNNING

    def maxIdle(self):
        '''
        On production environments, will return no idle for non removable machines
        '''
        if self._idle <= 0 or (settings.DEBUG is False and self._onLogout != 'remove'):
            return None

        return self._idle

    def marshal(self):
        '''
        Serializes the os manager data so we can store it in database
        '''
        return '\t'.join(['v2', self._onLogout, six.text_type(self._idle)])

    def unmarshal(self, s):
        data = s.split('\t')
        try:
            if data[0] == 'v1':
                self._onLogout = data[1]
                self._idle = -1
            elif data[0] == 'v2':
                self._onLogout, self._idle = data[1], int(data[2])
        except Exception:
            logger.exception('Exception unmarshalling. Some values left as default ones')

        self.__setProcessUnusedMachines()

    def valuesDict(self):
        return {'onLogout': self._onLogout, 'idle': self._idle}
