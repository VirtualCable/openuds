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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from django.utils.translation import ugettext_noop as _, ugettext
from uds.core.transports import protocols
from uds.core.services import Service, types as serviceTypes
from .OGDeployment import OGDeployment
from .OGPublication import OGPublication
from . import helpers

from uds.core.ui import gui

import logging

__updated__ = '2017-05-18'

logger = logging.getLogger(__name__)


class OGService(Service):
    '''
    OpenGnsys Service
    '''
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenGnsys Machines Service')
    # : Type used internally to identify this provider
    typeType = 'openGnsysMachine'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenGnsys physical machines')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    iconFile = 'provider.png'

    # Functional related data

    # : If the service provides more than 1 "deployed user" (-1 = no limit,
    # : 0 = ???? (do not use it!!!), N = max number to deploy
    maxDeployed = -1
    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is usesCache is True, you will need also
    # : set publicationType, do take care about that!
    usesCache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cacheTooltip = _('Number of desired machines to keep running waiting for an user')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = False
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = OGPublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = OGDeployment

    allowedProtocols = protocols.GENERIC
    servicesTypeProvided = (serviceTypes.VDI,)

    # Now the form part
    ou = gui.ChoiceField(
        label=_("OU"),
        order=100,
        fills={
            'callbackName' : 'osFillData',
            'function' : helpers.getResources,
            'parameters' : ['ov', 'ev', 'ou']
            },
        tooltip=_('Organizational Unit'),
        required=True
    )

    # Lab is not required, but maybe used as filter
    lab = gui.ChoiceField(
        label=_("lab"),
        order=101,
        tooltip=_('Laboratory'),
        required=False
    )

    # Required, this is the base image
    image = gui.ChoiceField(
        label=_("OS Image"),
        order=102,
        tooltip=_('OpenGnsys Operanting System Image'),
        required=True
    )

    maxReservationTime = gui.NumericField(
        length=3,
        label=_("Max. reservation time"),
        order=110,
        tooltip=_('Security parameter for OpenGnsys to kepp reservations at most this hours'),
        defvalue='24',
        tab=_('Advanced'),
        required=False
    )

    ov = gui.HiddenField(value=None)
    ev = gui.HiddenField(value=None)  # We need to keep the env so we can instantiate the Provider

    def initialize(self, values):
        '''
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        '''
        if values is not None:
            pass

    def initGui(self):
        '''
        Loads required values inside
        '''
        ous = [gui.choiceItem(r['id'], r['name']) for r in self.parent().api.getOus()]
        self.ou.setValues(ous)

        self.ov.setDefValue(self.parent().serialize())
        self.ev.setDefValue(self.parent().env.key)

    def status(self, machineId):
        return self.parent().status(machineId)

    def reserve(self):
        return self.parent().reserve(self.ou.value, self.image.value, self.lab.value, self.maxReservationTime.num())

    def unreserve(self, machineId):
        return self.parent().unreserve(machineId)
