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

from django.utils.translation import ugettext_noop as _
from uds.core.util.State import State
from uds.core.util.stats.events import addEvent, ET_LOGIN, ET_LOGOUT
from uds.core.util import log
from uds.core import Module

__updated__ = '2015-01-26'

STORAGE_KEY = 'osmk'


class OSManager(Module):
    '''
    An OS Manager is responsible for communication the service the different actions to take (i.e. adding a windows machine to a domain)
    The Service (i.e. virtual machine) communicates with the OSManager via a published web method, that must include the unique ID.
    In order to make easier to agents identify themselfs, the Unique ID can be a list with various Ids (i.e. the macs of the virtual machine).
    Server will iterate thought them and look for an identifier associated with the service. This list is a comma separated values (i.e. AA:BB:CC:DD:EE:FF,00:11:22:...)
    Remember also that we inherit the test and check methods from BaseModule
    '''
    # Service informational related data
    typeName = _('Base OS Manager')
    typeType = 'BaseOSManager'
    typeDescription = _('Base Manager')
    iconFile = 'osmanager.png'

    # If true, this os manager  will be invoked with every user service assigned, but not used
    # The interval is defined as a global config
    processUnusedMachines = False

    def __init__(self, environment, values):
        super(OSManager, self).__init__(environment, values)
        self.initialize(values)

    def initialize(self, values):
        '''
        This method will be invoked from __init__ constructor.
        This is provided so you don't have to provide your own __init__ method,
        and invoke base methods.
        This will get invoked when all initialization stuff is done

        Args:
            Values: If values is not none, this object is being initialized
            from administration interface, and not unmarshal will be done.
            If it's None, this is initialized internally, and unmarshal will
            be called after this.

        Default implementation does nothing
        '''
        pass

    def release(self, service):
        '''
        Called by a service that is in Usable state before destroying it so osmanager can release data associated with it
        Only invoked for services that reach the state "removed"
        @return nothing
        '''
        pass

    # These methods must be overriden
    def process(self, service, message, data, options=None):
        '''
        This method must be overriden so your so manager can manage requests and responses from agent.
        @param service: Service that sends the request (virtual machine or whatever)
        @param message: message to process (os manager dependent)
        @param data: Data for this message
        '''
        pass

    def checkState(self, service):
        '''
        This method must be overriden so your os manager can respond to requests from system to the current state of the service
        This method will be invoked when:
          * After service creation has finished, with the service wanting to see if it has to wait for os manager process finalization
          * After call to process method, to check if the state has changed
          * Before assigning a service to an user (maybe this is not needed)?
          Notice that the service could be in any state. In fact, what we want with this is return FINISHED if nothing is expected from os o RUNING else
          The state will be updated by actors inside oss, so no more direct checking is needed
          @return: RUNNING, FINISHED
          We do not expect any exception from this method
        '''
        return State.FINISHED

    def processUnused(self, userService):
        '''
        This will be invoked for every assigned and unused user service that has been in this state at least 1/2 of Globalconfig.CHECK_UNUSED_TIME
        This function can update userService values. Normal operation will be remove machines if this state is not valid
        '''
        pass

    def maxIdle(self):
        '''
        If os manager request "max idle", this method will return a value different to None so actors will get informed on Connection
        @return Must return None (default if not overriden), or a "max idle" in seconds
        '''
        return None

    @classmethod
    def transformsUserOrPasswordForService(cls):
        '''
        Helper method that informs if the os manager transforms the username and/or the password.
        This is used from DeployedService
        '''
        return cls.processUserPassword != OSManager.processUserPassword

    def processUserPassword(self, service, username, password):
        '''
        This will be invoked prior to passsing username/password to Transport.

        This method allows us to "change" username and/or password "on the fly".
        One example of use of this is an OS Manager that creates a random password for an user.
        In that case, this method, if the username passed in is the same as the os manager changes the password for, return the changed password.

        MUST Return:
            An array with 2 elements, [newUserName, newPassword].
            Default method simply does nothing with in parameters, just returns it. (So, if your os manager does not need this,
            simply do not implement it)

        Note: This method is, right now, invoked by Transports directly. So if you implement a Transport, remember to invoke this
        '''
        return [username, password]

    def destroy(self):
        '''
        Invoked when OS Manager is deleted
        '''
        pass

    def logKnownIp(self, userService, ip):
        userService.logIP(ip)

    def loggedIn(self, userService, userName=None, save=True):
        '''
        This method:
          - Add log in event to stats
          - Sets service in use
          - Invokes userLoggedIn for user service instance
        '''
        addEvent(userService.deployed_service, ET_LOGIN, fld1=userName)

        log.doLog(userService, log.INFO, "User {0} has logged in", log.OSMANAGER)

        userService.setInUse(True)
        si = userService.getInstance()
        si.userLoggedIn(userName)
        userService.updateData(si)
        if save:
            userService.save()

    def loggedOut(self, userService, userName=None, save=True):
        '''
        This method:
          - Add log in event to stats
          - Sets service in use
          - Invokes userLoggedIn for user service instance
        '''
        addEvent(userService.deployed_service, ET_LOGOUT, fld1=userName)
        log.doLog(userService, log.INFO, "User {0} has logged out", log.OSMANAGER)

        userService.setInUse(False)
        si = userService.getInstance()
        si.userLoggedOut(userName)
        userService.updateData(si)
        if save:
            userService.save()

    def __str__(self):
        return "Base OS Manager"

    def __unicode__(self):
        return self.__str__()
