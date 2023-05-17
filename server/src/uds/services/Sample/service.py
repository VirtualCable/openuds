# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _
from uds.core import services, exceptions
from uds.core.ui import gui

from .publication import SamplePublication
from .deployment_one import SampleUserDeploymentOne
from .deployment_two import SampleUserDeploymentTwo


# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.module import Module
    from uds.core.environment import Environment

logger = logging.getLogger(__name__)


class ServiceOne(services.Service):
    """
    Basic service, the first part (variables) include the description of the service.

    Remember to fill all variables needed, but at least you must define:
        * typeName
        * typeType
        * typeDescription
        * iconFile (defaults to service.png)
        * publicationType, type of publication in case it needs publication.
          If this is not provided, core will assume that the service do not
          needs publishing.
        * deployedType, type of deployed user service. Do not forget this!!!

    The rest of them can be ommited, but its recommended that you fill all
    declarations shown in this sample (that in fact, are all)

    This description informs the core what this service really provides,
    and how this is done. Look at description of class variables for more
    information.

    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    typeName = _('Sample Service One')
    # : Type used internally to identify this provider
    typeType = 'SampleService1'
    # : Description shown at administration interface for this provider
    typeDescription = _('Sample (and dummy) service ONE')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    iconFile = 'service.png'

    # Functional related data

    # : If the service provides more than 1 "deployed user" (-1 = no limit,
    # : 0 = ???? (do not use it!!!), N = max number to deploy
    maxDeployed = -1
    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is usesCache is True, you will need also
    # : set publicationType, do take care about that!
    usesCache = False
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cacheTooltip = _('None')
    # : If we need to generate a "Level 2" cache for this service (i.e., L1
    # : could be running machines and L2 suspended machines)
    usesCache_L2 = False
    # : Tooltip shown to user when this item is pointed at admin interface, None
    # : also because we don't use it
    cacheTooltip_L2 = _('None')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needsManager = False
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    mustAssignManually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publicationType = None
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = SampleUserDeploymentOne

    # Now the form part, this service will have only two "dummy" fields
    # If we don't indicate an order, the output order of fields will be
    # "random"

    colour = gui.ChoiceField(
        order=1,
        label=_('Colour'),
        tooltip=_('Colour of the field'),
        # In this case, the choice can have none value selected by default
        required=True,
        values=[
            gui.choiceItem('red', 'Red'),
            gui.choiceItem('green', 'Green'),
            gui.choiceItem('blue', 'Blue'),
            gui.choiceItem('nonsense', 'Blagenta'),
        ],
        defvalue='1',  # Default value is the ID of the choicefield
    )

    passw = gui.PasswordField(
        order=2,
        label=_('Password'),
        tooltip=_('Password for testing purposes'),
        required=True,
        defvalue='1234',  # : Default password are nonsense?? :-)
    )

    baseName = gui.TextField(
        order=3,
        label=_('Services names'),
        tooltip=_('Base name for this user services'),
        # In this case, the choice can have none value selected by default
        required=True,
        defvalue='',  # Default value is the ID of the choicefield
    )

    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        We check here form values to see if they are valid.

        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        """

        # We don't need to check anything, bat because this is a sample, we do
        # As in provider, we receive values only at new Service creation,
        # so we only need to validate params if values is not None
        if values:
            if self.colour.value == 'nonsense':
                raise exceptions.ValidationError(
                    'The selected colour is invalid!!!'
                )

    # Services itself are non testeable right now, so we don't even have
    # to provide one!!!

    # Congratulations!!!, the needed part of your first simple service is done!
    # Now you can go to administration panel, and check it
    #
    # From now onwards, we implement our own methods, that will be used by,
    # for example, services derived from this provider

    def getColour(self) -> str:
        """
        Simply returns colour, for deployed user services.

        Remember that choiceField.value returns the id part of the ChoiceItem
        """
        return self.colour.value

    def getPassw(self) -> str:
        """
        Simply returns passwd, for deloyed user services
        """
        return self.passw.value

    def getBaseName(self) -> str:
        return self.baseName.value


class ServiceTwo(services.Service):
    """
    Just a second service, no comments here (almost same that ServiceOne
    """

    typeName = _('Sample Service Two')
    typeType = 'SampleService2'
    typeDescription = _('Sample (and dummy) service ONE+ONE')
    iconFile = 'provider.png'  # : We reuse provider icon here :-)

    # Functional related data
    maxDeployed = 5
    usesCache = True
    cacheTooltip = _('L1 cache for dummy elements')
    usesCache_L2 = True
    cacheTooltip_L2 = _('L2 cache for dummy elements')

    needsManager = False
    mustAssignManually = False

    # : Types of publications. In this case, we will include a publication
    # : type for this one
    # : Note that this is a MUST if you indicate that needPublication
    publicationType = SamplePublication
    # : Types of deploys (services in cache and/or assigned to users)
    deployedType = SampleUserDeploymentTwo

    # Gui, we will use here the EditableList field
    names = gui.EditableListField(label=_('List of names'))

    def __init__(self, environment, parent, values=None):
        """
        We here can get a HUGE list from client.
        Right now, this is treated same as other fields, in a near
        future we will se how to handle this better
        """
        super(ServiceTwo, self).__init__(environment, parent, values)

        # No checks here

    def getNames(self) -> str:
        """
        For using at deployed services, really nothing
        """
        return self.names.value
