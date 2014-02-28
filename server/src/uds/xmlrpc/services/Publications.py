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

from uds.models import DeployedService, DeployedServicePublication, State
from django.utils.translation import ugettext as _
from ..util.Helpers import dictFromData
from ..auths.AdminAuth import needs_credentials
from ..util.Exceptions import PublicationException
from uds.core.managers.PublicationManager import PublicationManager
import logging

logger = logging.getLogger(__name__)

def dictFromPublication(pub):
    res = { 'idParent' : str(pub.deployed_service_id), 'id' : str(pub.id),
                    'state' : pub.state, 'publishDate' : pub.publish_date, 'reason' : State.toString(pub.state), 'revision' : str(pub.revision)
    }
    if State.isErrored(pub.state):
        publication = pub.getInstance()
        res['reason'] = publication.reasonOfError()
    return res

@needs_credentials
def getPublications(credentials, idParent):

    dps = DeployedService.objects.get(pk=idParent)
    res = []
    for pub in dps.publications.all().order_by('-publish_date'):
        try:
            val = dictFromPublication(pub)
            res.append(val)
        except Exception, e:
            logger.debug(e)
    return res

@needs_credentials
def publishDeployedService(credentials, idParent):
    try:
        ds = DeployedService.objects.get(pk=idParent)
        ds.publish()
    except Exception, e:
        raise PublicationException(unicode(e))
    return True

@needs_credentials
def cancelPublication(credentials, id):
    try:
        ds = DeployedServicePublication.objects.get(pk=id)
        ds.cancel()
    except Exception, e:
        raise PublicationException(unicode(e))
    return True


# Registers XML RPC Methods
def registerPublicationsFunctions(dispatcher):
    dispatcher.register_function(getPublications, 'getPublications')
    dispatcher.register_function(publishDeployedService, 'publishDeployedService')
    dispatcher.register_function(cancelPublication, 'cancelPublication')
