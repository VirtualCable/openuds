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

from django.conf.urls import patterns, include, url
from uds.core.util.modfinder import loadModulesUrls
from uds import REST

js_info_dict = {
    'domain': 'djangojs',
    'packages': ('uds',),
}

urlpatterns = patterns(
    'uds',
    url(r'^$', 'web.views.index', name='Index'),
    (r'^login/$', 'web.views.login'),
    (r'^login/(?P<tag>.+)$', 'web.views.login'),
    (r'^logout$', 'web.views.logout'),
    # Icons
    (r'^transicon/(?P<idTrans>.+)$', 'web.views.transportIcon'),
    # Images
    (r'^srvimg/(?P<idImage>.+)$', 'web.views.serviceImage'),
    url(r'^galimg/(?P<idImage>.+)$', 'web.views.image', name='galleryImage'),
    # Error URL
    (r'^error/(?P<idError>.+)$', 'web.views.error'),
    # Transport own link processor
    url(r'^trans/(?P<idService>.+)/(?P<idTransport>.+)$', 'web.views.transportOwnLink', name='TransportOwnLink'),
    # Authenticators custom html
    (r'^customAuth/(?P<idAuth>.*)$', 'web.views.customAuth'),
    # Preferences
    (r'^prefs$', 'web.views.prefs'),
    # Change Language
    (r'^i18n/', include('django.conf.urls.i18n')),
    # Downloads
    (r'^idown/(?P<idDownload>[a-zA-Z0-9-]*)$', 'web.views.download'),
    # downloads for client
    url(r'^down$', 'web.views.client_downloads', name='ClientDownload'),
    (r'^down/(?P<os>[a-zA-Z0-9-]*)$', 'web.views.client_downloads'),
    url(r'^pluginDetection/(?P<detection>[a-zA-Z0-9-]*)$', 'web.views.plugin_detection', name='PluginDetection'),
    # Client access enabler
    url(r'^enable/(?P<idService>.+)/(?P<idTransport>.+)$', 'web.views.clientEnabler', name='ClientAccessEnabler'),

    # Custom authentication callback
    (r'^auth/(?P<authName>.+)', 'web.views.authCallback'),
    (r'^authinfo/(?P<authName>.+)', 'web.views.authInfo'),
    (r'^about', 'web.views.about'),
    # Ticket authentication
    url(r'^tkauth/(?P<ticketId>.+)$', 'web.views.ticketAuth', name='TicketAuth'),

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
