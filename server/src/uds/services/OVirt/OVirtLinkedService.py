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

from django.utils.translation import ugettext_noop as translatable, ugettext as _
from uds.core.services import Service
from OVirtPublication import OVirtPublication
from OVirtLinkedDeployment import OVirtLinkedDeployment

from uds.core.ui import gui

import logging

logger = logging.getLogger(__name__)

from Helpers import oVirtHelpers

class OVirtLinkedService(Service):
    '''
    oVirt Linked clones service. This is based on creating a template from selected vm, and then use it to 
    
    
    '''
    #: Name to show the administrator. This string will be translated BEFORE
    #: sending it to administration interface, so don't forget to
    #: mark it as translatable (using ugettext_noop)
    typeName = translatable('oVirt Linked Clone') 
    #: Type used internally to identify this provider
    typeType = 'oVirtLinkedService'
    #: Description shown at administration interface for this provider
    typeDescription = translatable('oVirt Services based on templates and COW')
    #: Icon file used as icon for this provider. This string will be translated 
    #: BEFORE sending it to administration interface, so don't forget to
    #: mark it as translatable (using ugettext_noop)
    iconFile = 'service.png'
    
    # Functional related data
    
    #: If the service provides more than 1 "deployed user" (-1 = no limit, 
    #: 0 = ???? (do not use it!!!), N = max number to deploy
    maxDeployed = -1
    #: If we need to generate "cache" for this service, so users can access the 
    #: provided services faster. Is usesCache is True, you will need also 
    #: set publicationType, do take care about that!
    usesCache = True
    #: Tooltip shown to user when this item is pointed at admin interface, none 
    #: because we don't use it
    cacheTooltip = translatable('Number of desired machines to keep running waiting for a user')
    #: If we need to generate a "Level 2" cache for this service (i.e., L1 
    #: could be running machines and L2 suspended machines) 
    usesCache_L2 = False 
    #: Tooltip shown to user when this item is pointed at admin interface, None 
    #: also because we don't use it
    cacheTooltip_L2 = translatable('Number of desired machines to keep suspended waiting for use') 
      
    #: If the service needs a s.o. manager (managers are related to agents 
    #: provided by services itselfs, i.e. virtual machines with actors)
    needsManager = True
    #: If true, the system can't do an automatic assignation of a deployed user 
    #: service from this service
    mustAssignManually = False 

    #: Types of publications (preparated data for deploys) 
    #: In our case, we do no need a publication, so this is None
    publicationType = OVirtPublication
    #: Types of deploys (services in cache and/or assigned to users)
    deployedType = OVirtLinkedDeployment
    
    # Now the form part
    machine = gui.ChoiceField(label=translatable("Base Machine"), order = 1, tooltip = _('Service base machine'), required = True)
    cluster = gui.ChoiceField(label=translatable("Cluster"), order = 2, 
        fills = {
            'callbackName' : 'ovFillResourcesFromCluster', 
            'function' : oVirtHelpers.getResources, 
            'parameters' : ['cluster', 'ov', 'ev']
            },
        tooltip = translatable("Cluster to contain services"),  required = True                 
    )
    
    datastore =  gui.ChoiceField(label = translatable("Datastore Domain"), rdonly = False, order = 3, 
                                       tooltip = translatable('Datastore domain where to publish and put incrementals'), required = True)
    baseName = gui.TextField(label = translatable('Machine Names'), rdonly = False, order = 4, tooltip = ('Base name for clones from this machine'), required = True)
    lenName = gui.NumericField(length = 1, label = translatable('Name Length'), defvalue = 3, order = 5, 
                               tooltip = translatable('Length of numeric part for the names of this machines (betwen 3 and 6'), required = True)
    
    ov = gui.HiddenField()
    ev = gui.HiddenField() # We need to keep the env so we can instantiate the Provider
    
    def initialize(self, values):
        '''
        We check here form values to see if they are valid.
        
        Note that we check them throught FROM variables, that already has been
        initialized by __init__ method of base class, before invoking this.
        '''
        if values is not None:
            length = int(self.lenName.value)
            if len(self.baseName.value) + length > 15:
                raise Service.ValidationException(_('The length of basename plus length must not be greater than 15'))
            if self.baseName.value.isdigit():
                raise Service.ValidationException(_('The machine name can\'t be only numbers'))

        machines = self.parent().getMachines()
        vals = []
        for m in machines:
            vals.append( gui.choiceItem( m['id'], m['name'] ))
        self.machine.setValues(vals)
        
        clusters = self.parent().getClusters()
        vals = []
        for c in clusters:
            vals.append( gui.choiceItem(c['id'],  c['name'] ) )
        self.cluster.setValues(vals)
            
        
    def initGui(self):
        self.ov.value = self.parent().serialize()
        self.ev.value = self.parent().env().key()
        
