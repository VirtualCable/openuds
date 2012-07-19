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

"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TestCase
from uds.xmlrpc.util.TestTransport import rpcServer
from uds.xmlrpc.ServiceProviders import *
from models import *

class XmlRpcTest(TestCase):
    def setUp(self):
        #self.Provider1 = ServiceProviders.objects.create(name="Dummy 1", type="DummyProvider")
        #self.Provider2 = ServiceProviders.objects.create(name="Dummy 2", type="DummyProvider")
        return
        
    def testProviders(self):
        """
        Test the services providers api
        """
        credentials = rpcServer.login('','','')
        credentials = credentials['credentials']
        #rpcServer.createServiceProvider('prueba', '', r['type'], result )
        data = [ { 'name' : 'host' ,'value' : '192.168.0.15' }, 
                { 'name' : 'port' ,'value' : '443' },
                { 'name' : 'username' ,'value' : 'admin' },
                { 'name' : 'password' ,'value' : 'temporal' },
                ]
        rpcServer.testServiceProvider(credentials, 'VmwareVCServiceProvider', data)
        
        