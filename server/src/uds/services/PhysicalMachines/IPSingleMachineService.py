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
from uds.core.services import types as serviceTypes
from uds.core.ui.UserInterface import gui
from .IPMachineDeployed import IPMachineDeployed
import logging
import pickle

logger = logging.getLogger(__name__)


class IPSingleMachineService(services.Service):

    # Gui
    ip = gui.TextField(length=64, label=_('Machine IP'), order=1, tooltip=_('Machine IP'), required=True)


    # Description of service
    typeName = _('Static Single IP')
    typeType = 'IPSingleMachineService'
    typeDescription = _('This service provides access to POWERED-ON Machine by IP')
    iconFile = 'machine.png'

    # Characteristics of service
    maxDeployed = -1  # If the service provides more than 1 "provided service" (-1 = no limit, 0 = ???? (do not use it!!!), N = max number to deploy
    usesCache = False  # Cache are running machine awaiting to be assigned
    usesCache_L2 = False  # L2 Cache are running machines in suspended state
    needsManager = False  # If the service needs a s.o. manager (managers are related to agents provided by services itselfs, i.e. virtual machines with agent)
    mustAssignManually = False  # If true, the system can't do an automatic assignation of a deployed user service from this service

    deployedType = IPMachineDeployed

    servicesTypeProvided = (serviceTypes.VDI,)

    def initialize(self, values):
        pass

    def getUnassignedMachine(self):
        ip = None
        try:
            self.storage.lock()
            counter = self.storage.getPickle('counter')
            counter = counter + 1 if counter is not None else 1
            self.storage.putPickle('counter', counter)
            ip = '{}~{}'.format(self.ip.value, counter)
        except Exception:
            ip = None
            logger.exception("Exception at getUnassignedMachine")
        finally:
            self.storage.unlock()

        return ip

    def unassignMachine(self, ip):
        pass
