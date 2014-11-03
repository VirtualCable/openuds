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

js_info_dict = {
    'domain': 'djangojs',
    'packages': ('uds',),
}


from django.conf.urls import patterns, include, url
from uds.core.util.modfinder import loadModulesUrls
from uds import REST

urlpatterns = patterns(
    'uds',
    (r'^$', 'web.views.index'),
    (r'^login/$', 'web.views.login'),
    (r'^login/(?P<smallName>.+)$', 'web.views.login'),
    (r'^logout$', 'web.views.logout'),
    (r'^service/(?P<idService>.+)/(?P<idTransport>.+)$', 'web.views.service'),
    # Icons
    (r'^transicon/(?P<idTrans>.+)$', 'web.views.transportIcon'),
    # Images
    (r'^srvimg/(?P<idImage>.+)$', 'web.views.serviceImage'),
    # Error URL
    (r'^error/(?P<idError>.+)$', 'web.views.error'),
    # Transport component url
    (r'^transcomp/(?P<idTransport>.+)/(?P<componentId>.+)$', 'web.views.transcomp'),
    # Service notification url
    (r'^sernotify/(?P<idUserService>.+)/(?P<notification>.+)$', 'web.views.sernotify'),
    # Authenticators custom html
    (r'^customAuth/(?P<idAuth>.*)$', 'web.views.customAuth'),
    # Preferences
    (r'^prefs$', 'web.views.prefs'),
    # Change Language
    (r'^i18n/', include('django.conf.urls.i18n')),
    # Downloadables
    (r'^download/(?P<idDownload>[a-zA-Z0-9-]*)$', 'web.views.download'),
    # Custom authentication callback
    (r'^auth/(?P<authName>.+)', 'web.views.authCallback'),
    (r'^authJava/(?P<idAuth>.+)/(?P<hasJava>.*)$', 'web.views.authJava'),
    (r'^authinfo/(?P<authName>.+)', 'web.views.authInfo'),
    (r'^about', 'web.views.about'),
    # Ticket authentication
    url(r'^tkauth/(?P<ticketId>.+)$', 'web.views.ticketAuth', name='TicketAuth'),


    # XMLRPC Processor
    (r'^xmlrpc$', 'xmlrpc.views.xmlrpc'),

    # REST Api
    url(r'^rest/(?P<arguments>.*)$', REST.Dispatcher.as_view(), name="REST"),

    # Web admin GUI
    (r'^adm/', include('uds.admin.urls')),

    # Internacionalization in javascript
    # Javascript catalog
    (r'^jsi18n/(?P<lang>[a-z]*)$', 'web.views.jsCatalog', js_info_dict),

)

# Append urls from special dispatchers
urlpatterns += loadModulesUrls()
