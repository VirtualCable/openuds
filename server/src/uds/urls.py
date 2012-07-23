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

from django.conf.urls.defaults import patterns, include
from uds.core.util.modfinder import loadModulesUrls

urlpatterns = patterns('uds',
    (r'^$', 'web.views.index'),
    (r'^login/$', 'web.views.login'),
    (r'^logout$', 'web.views.logout'),
    (r'^service/(?P<idService>.+)/(?P<idTransport>.+)$', 'web.views.service'),
    # Icons
    (r'^transicon/(?P<idTrans>.+)$', 'web.views.transportIcon'),
    # Error URL
    (r'^error/(?P<idError>.+)$', 'web.views.error'),
    # Transport component url
    (r'^transcomp/(?P<idTransport>.+)/(?P<componentId>.+)$', 'web.views.transcomp'),
    # Authenticators custom html
    (r'^customAuth/(?P<idAuth>.*)$', 'web.views.customAuth'),
    # Preferences
    (r'^prefs$', 'web.views.prefs'),
    # Change Language
    (r'^i18n/', include('django.conf.urls.i18n')),
    # Downloadables
    (r'^download/(?P<idDownload>.*)$', 'web.views.download'),
    # XMLRPC Processor
    (r'^xmlrpc$', 'xmlrpc.views.xmlrpc'),
    # Custom authentication callback
    (r'^auth/(?P<idAuth>.+)', 'web.views.authCallback'),
    (r'^authJava/(?P<idAuth>.+)/(?P<hasJava>.*)$', 'web.views.authJava'),
    (r'^authinfo/(?P<authName>.+)', 'web.views.authInfo'),
    
)

# Append urls from special dispatcher
urlpatterns += loadModulesUrls()
