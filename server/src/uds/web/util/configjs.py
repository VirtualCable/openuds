# -*- coding: utf-8 -*-
#
# Copyright (c) 2018-2019 Virtual Cable S.L.
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
import typing

from django import template
from django.conf import settings
from django.utils.translation import gettext, get_language
from django.urls import reverse
from django.templatetags.static import static

from uds.REST import AUTH_TOKEN_HEADER
from uds.REST.methods.client import CLIENT_VERSION
from uds.core.managers import downloadsManager
from uds.core.util.config import GlobalConfig
from uds.core import VERSION, VERSION_STAMP
from uds.models import Authenticator, Image, Network, Transport

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequest
    from uds.models import User

logger = logging.getLogger(__name__)

register = template.Library()

CSRF_FIELD = 'csrfmiddlewaretoken'


@register.simple_tag(takes_context=True)
def udsJs(request: 'ExtendedHttpRequest') -> str:
    auth_host = (
        request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'
    )  # Last one is a placeholder in case we can't locate host name

    role: str = 'user'
    user: typing.Optional['User'] = request.user if request.authorized else None

    if user:
        role = (
            'staff'
            if user.isStaff() and not user.is_admin
            else 'admin'
            if user.is_admin
            else 'user'
        )
        if request.session.get('restricted', False):
            role = 'restricted'

    profile: typing.Dict[str, typing.Any] = {
        'user': user.name if user else None,
        'role': role,
    }

    tag = request.session.get('tag', None)
    logger.debug('Tag config: %s', tag)
    if GlobalConfig.DISALLOW_GLOBAL_LOGIN.getBool():
        try:
            # Get authenticators with auth_host or tag. If tag is None, auth_host, if exists
            # tag, later will remove "auth_host"
            authenticators = Authenticator.objects.filter(
                small_name__in=[auth_host, tag]
            )[:]
        except Exception as e:
            authenticators = []
    else:
        authenticators = list(Authenticator.objects.all().exclude(visible=False))

    # Filter out non visible authenticators
    authenticators = [a for a in authenticators if a.getInstance().isVisibleFrom(request)]

    # logger.debug('Authenticators PRE: %s', authenticators)

    if (
        tag and authenticators
    ):  # Refilter authenticators, visible and with this tag if required
        authenticators = [
            x
            for x in authenticators
            if x.small_name == tag
            or (tag == 'disabled' and x.getType().isCustom() is False)
        ]

    if not authenticators and tag != 'disabled':
        try:
            authenticators = [Authenticator.objects.order_by('priority')[0]]
        except Exception:  # There is no authenticators yet...
            authenticators = []

    if not tag and authenticators:
        tag = authenticators[0].small_name

    # logger.debug('Authenticators: %s', authenticators)

    # the auths for client
    def getAuthInfo(auth: Authenticator):
        theType = auth.getType()
        return {
            'id': auth.uuid,
            'name': auth.name,
            'label': auth.small_name,
            'priority': auth.priority,
            'is_custom': theType.isCustom(),
        }

    config = {
        'version': VERSION,
        'version_stamp': VERSION_STAMP,
        'language': get_language(),
        'available_languages': [
            {'id': k, 'name': gettext(v)} for k, v in settings.LANGUAGES
        ],
        'authenticators': [
            getAuthInfo(auth) for auth in authenticators if auth.getType()
        ],
        'mfa': request.session.get('mfa', None),
        'tag': tag,
        'os': request.os['OS'].value[0],
        'image_size': Image.MAX_IMAGE_SIZE,
        'experimental_features': GlobalConfig.EXPERIMENTAL_FEATURES.getBool(),
        'reload_time': GlobalConfig.RELOAD_TIME.getInt(True),
        'site_name': GlobalConfig.SITE_NAME.get(),
        'site_copyright_info': GlobalConfig.SITE_COPYRIGHT.get(),
        'site_copyright_link': GlobalConfig.SITE_COPYRIGHT_LINK.get(),
        'site_logo_name': GlobalConfig.SITE_LOGO_NAME.get(),
        'site_information': GlobalConfig.SITE_INFO.get(),
        'site_filter_on_top': GlobalConfig.SITE_FILTER_ONTOP.getBool(True),
        'launcher_wait_time': 5000,
        'messages': {
            # Calendar denied message
            'calendarDenied': GlobalConfig.LIMITED_BY_CALENDAR_TEXT.get().strip()
            or gettext('Access limited by calendar')
        },
        'urls': {
            'changeLang': reverse('set_language'),
            'login': reverse('page.login'),
            'mfa': reverse('page.mfa'),
            'logout': reverse('page.logout'),
            'user': reverse('page.index'),
            'customAuth': reverse('uds.web.views.customAuth', kwargs={'idAuth': ''}),
            'services': reverse('webapi.services'),
            'error': reverse('webapi.error', kwargs={'err': '9999'}),
            'enabler': reverse(
                'webapi.enabler',
                kwargs={'idService': 'param1', 'idTransport': 'param2'},
            ),
            'status': reverse(
                'webapi.status', kwargs={'idService': 'param1', 'idTransport': 'param2'}
            ),
            'action': reverse(
                'webapi.action',
                kwargs={'idService': 'param1', 'actionString': 'param2'},
            ),
            'galleryImage': reverse(
                'webapi.galleryImage', kwargs={'idImage': 'param1'}
            ),
            'transportIcon': reverse(
                'webapi.transportIcon', kwargs={'idTrans': 'param1'}
            ),
            'static': static(''),
            'clientDownload': reverse('page.client-download'),
            'updateTransportTicket': reverse('webapi.transport.UpdateTransportTicket', kwargs={'idTicket': 'param1', 'scrambler': 'param2'}),
            # Launcher URL if exists
            'launch': request.session.get('launch', ''),
            'brand': settings.UDSBRAND if hasattr(settings, 'UDSBRAND') else ''
        },
        'min_for_filter': GlobalConfig.SITE_FILTER_MIN.getInt(True),
    }

    info: typing.Optional[typing.MutableMapping] = None
    if user and user.isStaff():
        info = {
            'networks': [n.name for n in Network.networksFor(request.ip)],
            'transports': [
                t.name for t in Transport.objects.all() if t.validForIp(request.ip)
            ],
            'ip': request.ip,
            'ip_proxy': request.ip_proxy,
        }

    # all plugins are under url clients...
    plugins = [
        {
            'url': static('clients/' + url.format(version=CLIENT_VERSION)),
            'description': description,
            'name': name,
            'legacy': legacy,
        }
        for url, description, name, legacy in (
            (
                'UDSClientSetup-{version}.exe',
                gettext('Windows client'),
                'Windows',
                False,
            ),
            ('UDSClient-{version}.pkg', gettext('Mac OS X client'), 'MacOS', False),
            (
                'udsclient3_{version}_all.deb',
                gettext('Debian based Linux client')
                + ' '
                + gettext('(requires Python-3.6 or newer)'),
                'Linux',
                False,
            ),
            (
                'udsclient3-{version}-1.noarch.rpm',
                gettext('RPM based Linux client (Fedora, Suse, ...)')
                + ' '
                + gettext('(requires Python-3.6 or newer)'),
                'Linux',
                False,
            ),
            (
                'udsclient3-x86_64-{version}.tar.gz',
                gettext('Binary appimage X86_64 Linux client'),
                'Linux',
                False,
            ),
            (
                'udsclient3-armhf-{version}.tar.gz',
                gettext('Binary appimage Raspberry Linux client'),
                'Linux',
                False,
            ),
            (
                'udsclient3-{version}.tar.gz',
                gettext('Generic .tar.gz Linux client')
                + ' '
                + gettext('(requires Python-3.6 or newer)'),
                'Linux',
                False,
            ),
        )
    ]

    # We can add here custom downloads with something like this:
    # plugins.append({
    #     'url': 'http://www.google.com/coche.exe',
    #     'description': 'Cliente SPICE for download',  # Text that appears on download
    #     'name': 'Linux', # Can be 'Linux', 'Windows', o 'MacOS'. Sets the icon.
    #     'legacy': False  # True = Gray, False = White
    # })

    actors: typing.List[typing.Dict[str, str]] = []

    if user and user.isStaff():  # Add staff things
        # If is admin (informational, REST api checks users privileges anyway...)
        profile['admin'] = True
        # REST auth
        config['auth_token'] = request.session.session_key
        config['auth_header'] = AUTH_TOKEN_HEADER
        # Actors
        actors = [
            {
                'url': reverse('utility.downloader', kwargs={'idDownload': key}),
                'name': val['name'],
                'description': gettext(val['comment']),
            }
            for key, val in downloadsManager().getDownloadables().items()
        ]
        # URLS
        config['urls']['admin'] = reverse('uds.admin.views.index')
        config['urls']['rest'] = reverse('REST', kwargs={'arguments': ''})
        # Admin config
        page_size = GlobalConfig.ADMIN_PAGESIZE.getInt(True)
        vnc_userservices = GlobalConfig.ADMIN_ENABLE_USERSERVICES_VNC.getBool(True)
        # Fix page size to razonable usable values
        page_size = 10 if page_size < 10 else 100 if page_size > 100 else page_size
        config['admin'] = {
            'page_size': page_size,
            'vnc_userservices': vnc_userservices,
        }

    errors: typing.List = []
    if 'errors' in request.session:
        errors = request.session['errors']
        del request.session['errors']
        request.session.modified = True  # Ensure saves it

    uds = {
        'profile': profile,
        'config': config,
        'info': info,
        'plugins': plugins,
        'actors': actors,
        'errors': errors,
        'data': request.session.get('data'),
    }

    # Reset some 1 time values...
    request.session['launch'] = ''

    return 'var udsData = ' + json.dumps(uds) + ';\n'
