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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

from django.urls import re_path, path
from django.conf.urls import include
from django.views.i18n import JavaScriptCatalog
from django.views.generic.base import RedirectView

from uds import REST
from uds.core import types
import uds.web.views
import uds.admin.views

from uds.core.util.modfinder import loadModulesUrls


urlpatterns = [
    # Root url placeholder
    path(
        r'',
        RedirectView.as_view(pattern_name='page.index', permanent=False),
        name='page.index.placeholder',
    ),
    # path(r'', RedirectView.as_view(url='https://www.udsenterprise.com', permanent=False), name='page.index.placeholder')
    # START COMPAT redirections & urls
    path(
        r'login/',
        RedirectView.as_view(pattern_name='page.login', permanent=False),
        name='page.login.compat',
    ),
    path(
        r'logout/',
        RedirectView.as_view(pattern_name='page.logout'),
        name='page.logout.compat',
    ),
    # Backwards compatibility with REST API path
    re_path(r'^rest/(?P<arguments>.*)$', REST.Dispatcher.as_view(), name="REST.compat"),
    # Old urls for federated authentications
    re_path(
        r'^auth/(?P<authName>.+)',
        uds.web.views.auth_callback,
        name='page.auth.callback.compat',
    ),
    re_path(
        r'^authinfo/(?P<authName>.+)',
        uds.web.views.auth_info,
        name='page.auth.info.compat',
    ),
    # Ticket authentication
    re_path(
        r'^tkauth/(?P<ticketId>[a-zA-Z0-9-]+)$',
        uds.web.views.ticket_auth,
        name='page.auth.ticket.compat',
    ),
    # END COMPAT
    # Index
    path(r'uds/page/services', uds.web.views.main.index, name='page.index'),
    # Login/logout
    path(r'uds/page/login', uds.web.views.main.login, name=types.auth.AuthenticationInternalUrl.LOGIN.value),
    re_path(
        r'^uds/page/login/(?P<tag>[a-zA-Z0-9-]+)$',
        uds.web.views.main.login,
        name='page.login.tag',
    ),
    path(r'uds/page/logout', uds.web.views.main.logout, name='page.logout'),
    # MFA authentication
    path(r'uds/page/mfa/', uds.web.views.main.mfa, name='page.mfa'),
    # Error URL (just a placeholder, calls index with data on url for angular)
    re_path(
        r'^uds/page/error/(?P<err>[a-zA-Z0-9=-]+)$',
        uds.web.views.error,
        name='page.error',
    ),
    # Download plugins URL  (just a placeholder, calls index with data on url for angular)
    path(
        r'uds/page/client-download',
        uds.web.views.main.index,
        name='page.client-download',
    ),
    # Federated authentication
    re_path(
        r'^uds/page/auth/(?P<authName>[^/]+)$',
        uds.web.views.auth_callback,
        name='page.auth.callback',
    ),
    re_path(
        r'^uds/page/auth/stage2/(?P<ticketId>[^/]+)$',
        uds.web.views.auth_callback_stage2,
        name='page.auth.callback_stage2',
    ),
    re_path(
        r'^uds/page/auth/info/(?P<authName>[a-zA-Z0-9.-]+)$',
        uds.web.views.auth_info,
        name='page.auth.info',
    ),
    # Ticket authentication related
    re_path(
        r'^uds/page/ticket/auth/(?P<ticketId>[a-zA-Z0-9.-]+)$',
        uds.web.views.ticket_auth,
        name='page.ticket.auth',
    ),
    path(
        r'uds/page/ticket/launcher',
        uds.web.views.main.ticketLauncher,
        name='page.ticket.launcher',
    ),
    # This must be the last, so any patition will be managed by client in fact
    re_path(r'uds/page/.*', uds.web.views.main.index, name='page.placeholder'),
    # Utility
    path(r'uds/utility/closer', uds.web.views.service.closer, name='utility.closer'),
    # Javascript
    path(r'uds/utility/uds.js', uds.web.views.main.js, name="utility.js"),
    path(r'uds/adm/utility/uds.js', uds.web.views.main.js, name="utility-adm.js"),
    # i18n
    re_path(
        r'^uds/utility/i18n/(?P<lang>[a-z_-]*).js$',
        JavaScriptCatalog.as_view(),
        name='utility.jsCatalog',
    ),
    path(r'uds/utility/i18n', include('django.conf.urls.i18n')),
    # Downloader
    re_path(
        r'^uds/utility/download/(?P<idDownload>[a-zA-Z0-9-]*)$',
        uds.web.views.download,
        name='utility.downloader',
    ),
    # WEB API path (not REST api, frontend)
    re_path(
        r'^uds/webapi/img/transport/(?P<idTrans>[a-zA-Z0-9:-]+)$',
        uds.web.views.transportIcon,
        name='webapi.transportIcon',
    ),
    re_path(
        r'^uds/webapi/img/gallery/(?P<idImage>[a-zA-Z0-9-]+)$',
        uds.web.views.image,
        name='webapi.galleryImage',
    ),
    # Enabler and Status action are first processed, and if not match, execute the generic "action" handler
    re_path(
        r'^uds/webapi/action/(?P<idService>[a-zA-Z0-9:-]+)/enable/(?P<idTransport>[a-zA-Z0-9:-]+)$',
        uds.web.views.userServiceEnabler,
        name='webapi.enabler',
    ),
    re_path(
        r'^uds/webapi/action/(?P<idService>[a-zA-Z0-9:-]+)/status/(?P<idTransport>[a-zA-Z0-9:-]+)$',
        uds.web.views.userServiceStatus,
        name='webapi.status',
    ),
    re_path(
        r'^uds/webapi/action/(?P<idService>[a-zA-Z0-9:-]+)/(?P<actionString>[a-zA-Z0-9:-]+)$',
        uds.web.views.action,
        name='webapi.action',
    ),
    # Services list, ...
    path(
        r'uds/webapi/services',
        uds.web.views.main.servicesData,
        name='webapi.services',
    ),
    # Transport own link processor
    re_path(
        r'^uds/webapi/trans/(?P<idService>[a-zA-Z0-9:-]+)/(?P<idTransport>[a-zA-Z0-9:-]+)$',
        uds.web.views.transportOwnLink,
        name='TransportOwnLink',
    ),
    # Transport ticket update (for username/password on html5)
    re_path(
        r'^uds/webapi/trans/ticket/(?P<idTicket>[a-zA-Z0-9:-]+)/(?P<scrambler>[a-zA-Z0-9:-]+)$',
        uds.web.views.main.update_transport_ticket,
        name='webapi.transport.UpdateTransportTicket',
    ),
    # Authenticators custom js
    re_path(
        r'^uds/webapi/customAuth/(?P<idAuth>[a-zA-Z0-9:-]*)$',
        uds.web.views.custom_auth,
        name='uds.web.views.customAuth',
    ),
    # Error message
    re_path(
        r'^uds/webapi/error/(?P<err>[0-9]+)$',
        uds.web.views.errorMessage,
        name='webapi.error',
    ),
    # END WEB API
    # Custumization of GUI
    re_path(
        r'^uds/custom/(?P<component>[a-zA-Z.-]+)$',
        uds.web.views.custom.custom,
        name='custom',
    ),
    # REST API
    re_path(r'^uds/rest/(?P<arguments>.*)$', REST.Dispatcher.as_view(), name="REST"),
    # Web admin GUI
    re_path(r'^uds/adm/', uds.admin.views.index, name='uds.admin.views.index'),
]

# Append urls from special dispatchers
urlpatterns += loadModulesUrls()
