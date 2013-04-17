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

from django.utils.translation import ugettext as _
from django.db import IntegrityError 
from uds.models import Network, Transport
from uds.xmlrpc.util.Exceptions import InsertException, FindException, DeleteException
from uds.xmlrpc.auths.AdminAuth import needs_credentials
import logging

logger = logging.getLogger(__name__)

def dictFromNetwork(net):
    return  { 'id' : str(net.id), 'name' : net.name, 'netRange' : net.net_string }

@needs_credentials
def getNetworks(credentials):
    '''
    Returns the services providers managed (at database)
    '''
    res = []
    for net in Network.objects.all():
        res.append(dictFromNetwork(net))
    return res

@needs_credentials
def getNetworksForTransport(credentials, id_):
    try:
        res = [ str(n.id) for n in Transport.objects.get(pk=id_).networks.all().order_by('name') ]
    except Exception:
        res = []
    return res

@needs_credentials
def setNetworksForTransport(credentials, id_, networks):
    try:
        trans = Transport.objects.get(pk=id_)
        trans.networks = Network.objects.filter(id__in=networks)
    except Transport.DoesNotExist:
        raise FindException(_('Can\'t locate the transport') + '.' + _('Please, refresh interface'))
    return True

@needs_credentials
def getNetwork(credentials, id_):
    try:
        net = Network.objects.get(pk=id_)
    except Network.DoesNotExist:
        raise FindException(_('Can\'t locate the network') + '.' + _('Please, refresh interface'))
    return dictFromNetwork(net)

@needs_credentials
def createNetwork(credentials, network):
    try:
        Network.create(network['name'], network['netRange'])
    except IntegrityError:
        raise InsertException(_('Name %s already exists') % (network['name']))
    return True

@needs_credentials
def modifyNetwork(credentials, network):
    try:
        net = Network.objects.get(pk=network['id'])
        net.update(network['name'], network['netRange'])
    except Network.DoesNotExist:
        raise FindException(_('Can\'t locate the network') + '.' + _('Please, refresh interface'))
    except IntegrityError:
        raise InsertException(_('Name %s already exists') % (network['name']))
    return True

@needs_credentials
def removeNetworks(credentials, ids):
    try:
        Network.objects.filter(id__in=ids).delete()
    except Exception as e:
        raise DeleteException(unicode(e))
    return True

def registerNetworksFunctions(dispatcher):
    dispatcher.register_function(getNetworks, 'getNetworks')
    dispatcher.register_function(getNetworksForTransport, 'getNetworksForTransport')
    dispatcher.register_function(setNetworksForTransport, 'setNetworksForTransport')
    dispatcher.register_function(getNetwork, 'getNetwork')
    dispatcher.register_function(createNetwork, 'createNetwork')
    dispatcher.register_function(modifyNetwork, 'modifyNetwork')
    dispatcher.register_function(removeNetworks, 'removeNetworks')

