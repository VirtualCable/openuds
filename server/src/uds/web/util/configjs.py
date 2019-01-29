# -*- coding: utf-8 -*-

#
# Copyright (c) 2018 Virtual Cable S.L.
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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import json

import logging

from django import template
from django.conf import settings
from django.middleware import csrf
from django.utils.translation import gettext, get_language
from django.utils.html import mark_safe
from django.urls import reverse
from django.templatetags.static import static

from uds.REST import AUTH_TOKEN_HEADER
from uds.REST.methods.client import CLIENT_VERSION

from uds.core.managers import downloadsManager
from uds.core.util.Config import GlobalConfig

from uds.core import VERSION, VERSION_STAMP

from uds.models import Authenticator, Image

logger = logging.getLogger(__name__)

register = template.Library()

CSRF_FIELD = 'csrfmiddlewaretoken'


@register.simple_tag(takes_context=True)
def udsJs(request):
    auth_host = request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'  # Last one is a placeholder in case we can't locate host name

    profile = {
        'user': None if request.user is None else request.user.name,
        'role': 'staff' if request.user and request.user.staff_member else 'user',
    }

    # Gets csrf token
    csrf_token = csrf.get_token(request)
    if csrf_token is not None:
        csrf_token = str(csrf_token)

    if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool(False) is True:
        try:
            authenticators = [Authenticator.objects.get(small_name=auth_host)]
        except Exception:
            try:
                authenticators = [Authenticator.objects.order_by('priority')[0].small_name]
            except Exception:  # There is no authenticators yet...
                authenticators = []
    else:
        authenticators = Authenticator.objects.all()

    # the auths for client
    def getAuth(auth):
        theType = auth.getType()
        return {
            'id': auth.uuid,
            'name': auth.name,
            'label': auth.small_name,
            'priority': auth.priority,
            'is_custom': theType.isCustom()
        }

    config = {
        'version': VERSION,
        'version_stamp': VERSION_STAMP,
        'language': get_language(),
        'available_languages': [{'id': k, 'name': gettext(v)} for k, v in settings.LANGUAGES],
        'authenticators': [getAuth(auth) for auth in authenticators if auth.getType()],
        'os': request.os['OS'],
        'csrf_field': CSRF_FIELD,
        'csrf': csrf_token,
        'image_size': Image.MAX_IMAGE_SIZE,
        'urls': {
            'changeLang': reverse('set_language'),
            'login': reverse('page.login'),
            'logout': reverse('page.logout'),
            'user': reverse('page.index'),
            'customAuth': reverse('uds.web.views.customAuth', kwargs={'idAuth': ''}),
            'services': reverse('webapi.services'),
            'enabler': reverse('webapi.enabler', kwargs={ 'idService': 'param1', 'idTransport': 'param2' }),
            'action': reverse('webapi.action', kwargs={ 'idService': 'param1', 'action': 'param2' }),
            'galleryImage': reverse('webapi.galleryImage', kwargs={ 'idImage': 'param1' }),
            'transportIcon': reverse('webapi.transportIcon', kwargs={'idTrans': 'param1'}),
            'static': static(''),
        }
    }

    plugins = [
        {
            'url': static(url.format(version=CLIENT_VERSION)),
            'description': description,
            'name': name
        } for url, description, name in (
            ('clients/UDSClientSetup-{version}.exe', gettext('Windows client'), 'Windows'),
            ('clients/UDSClient-{version}.pkg', gettext('Mac OS X client'), 'MacOS'),
            ('udsclient_{version}_all.deb', gettext('Debian based Linux client') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-{version}-1.noarch.rpm', gettext('Red Hat based Linux client (RH, Fedora, Centos, ...)') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-opensuse-{version}-1.noarch.rpm', gettext('Suse based Linux client') + ' ' + gettext('(requires Python-2.7)'), 'Linux'),
            ('udsclient-{version}.tar.gz', gettext('Generic .tar.gz Linux client') + ' ' + gettext('(requires Python-2.7)'), 'Linux')
        )
    ]

    actors = []

    if profile['role'] == 'staff':  # Add staff things
        # If is admin (informational, REST api checks users privileges anyway...)
        profile['admin'] = True;
        # REST auth
        config['auth_token'] = request.session.session_key
        config['auth_header'] = AUTH_TOKEN_HEADER
        # Actors
        actors = [{'url': reverse('utility.downloader', kwargs={'idDownload': key}), 'name': val['name'], 'description': gettext(val['comment'])} for key, val in downloadsManager().getDownloadables().items()]
        # URLS
        config['urls']['admin'] = reverse('uds.admin.views.index')
        config['urls']['rest'] = reverse('REST', kwargs={'arguments': ''})

    errors = []
    if 'errors' in request.session:
        errors = request.session['errors']
        del request.session['errors']

    uds = {
        'profile': profile,
        'config': config,
        'plugins': plugins,
        'actors': actors,
        'errors': errors,
        'data': request.session.get('data')
    }

    return 'var udsData = ' + json.dumps(uds) + ';\n'

