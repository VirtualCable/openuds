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

from django.http import HttpResponse
from SimpleXMLRPCServer import SimpleXMLRPCDispatcher
from django.views.decorators.csrf import csrf_exempt

from services.ServiceProviders import registerServiceProvidersFunctions
from services.Services import registerServiceFunctions
from services.DeployedServices import registerDeployedServicesFunctions
from services.Publications import registerPublicationsFunctions
from services.UserDeployedServices import registerUserDeployedServiceFunctions
from actor.Actor import registerActorFunctions
from util.Callbacks import registerCallbackFunctions
from auths.AdminAuth import registerAdminAuthFunctions
from auths.Authenticators import  registerAuthenticatorFunctions
from osmanagers.OSManagers import registerOSManagersFunctions
from transports.Transports import registerTransportsFunctions
from transports.Networks import registerNetworksFunctions
from auths.Groups import registerGroupsFunctions
from auths.Users import registerUserFunctions
from auths.UserPreferences import registerPreferencesFunctions
from tools.Cache import registerCacheFunctions
from tools.Config import registerConfigurationFunctions

import logging

logger = logging.getLogger(__name__)

class XMLRPCDispatcher(SimpleXMLRPCDispatcher):
    '''
    Own dispatchers, to allow the pass of the request to the methods.
    
    Request will be, in most cases, removed from params at @needs_credentials decorator
    This means that all xmlrpc methods that needs_credentials, will have the request at
    the Credentials object.
    
    If no request is needed, normal method invocation will be done
    '''
    
    def __init__(self):
        SimpleXMLRPCDispatcher.__init__(self, allow_none=False, encoding=None)
        
        
    def dispatch(self, request, **kwargs):
        import xmlrpclib
        xml = request.raw_post_data
        try:
            params, method = xmlrpclib.loads(xml)
            try:
                response = self._dispatch(method, params + (request,))
            except TypeError:
                response = self._dispatch(method, params)
            
            response = (response,)
            response = xmlrpclib.dumps( response, methodresponse=1)
        except xmlrpclib.Fault as fault:
            response = xmlrpclib.dumps(fault)
        except Exception as e:
            response = xmlrpclib.dumps(
                xmlrpclib.Fault(1, "Exception caught!: {0}".format(e))
                )
        
        return HttpResponse(response, content_type = 'text/xml')
    

dispatcher = XMLRPCDispatcher()

# csrf_exempt is needed because we don't expect xmlrcp to be called from a web form
@csrf_exempt
def xmlrpc(request):
    if len(request.POST):
        response = dispatcher.dispatch(request)
    else:
        logger.error('XMLRPC invocation with GET method {0}'.format(request.path))
        response = HttpResponse()
        response.write("<b>This is an XML-RPC Service.</b><br>")
        response.write("You need to invoke it using an XML-RPC Client!<br>")
        #response.write("The following methods are available:<ul>")
        #methods = dispatcher.system_listMethods()
        #for method in methods:
                # right now, my version of SimpleXMLRPCDispatcher always
                # returns "signatures not supported"... :(
                # but, in an ideal world it will tell users what args are expected
        #        sig = dispatcher.system_methodSignature(method)

                # this just reads your docblock, so fill it in!
        #        help =  dispatcher.system_methodHelp(method)

        #        response.write("<li><b>%s</b>: [%s] %s" % (method, sig, help))

        # response.write("</ul>")

    response['Content-length'] = str(len(response.content))
    return response

# Register every xmlrpc function
registerServiceProvidersFunctions(dispatcher)
registerServiceFunctions(dispatcher)
registerPublicationsFunctions(dispatcher)
registerUserDeployedServiceFunctions(dispatcher)
registerOSManagersFunctions(dispatcher)
registerTransportsFunctions(dispatcher)
registerNetworksFunctions(dispatcher)
registerAdminAuthFunctions(dispatcher)
registerAuthenticatorFunctions(dispatcher)
registerGroupsFunctions(dispatcher)
registerUserFunctions(dispatcher)
registerCallbackFunctions(dispatcher)
registerDeployedServicesFunctions(dispatcher)
registerActorFunctions(dispatcher)
registerPreferencesFunctions(dispatcher)
registerCacheFunctions(dispatcher)
registerConfigurationFunctions(dispatcher)
