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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import json
import logging
import typing

from django import template
from django.conf import settings
from django.utils.translation import gettext, get_language
from django.urls import reverse
from django.templatetags.static import static

from uds.core import consts
from uds.core.managers import downloads_manager
from uds.core.util.config import GlobalConfig
from uds.models import Authenticator, Image, Network, Transport

from . import udsclients_info

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequest
    from uds.models import User

logger = logging.getLogger(__name__)

register = template.Library()


def uds_js(request: 'ExtendedHttpRequest') -> str:
    auth_host = (
        request.META.get('HTTP_HOST') or request.META.get('SERVER_NAME') or 'auth_host'
    )  # Last one is a placeholder in case we can't locate host name
    
    role: str = 'user'
    user: typing.Optional['User'] = request.user if request.authorized else None

    if user:
        role = 'staff' if user.is_staff() and not user.is_admin else 'admin' if user.is_admin else 'user'
        if request.session.get('restricted', False):
            role = 'restricted'

    profile: dict[str, typing.Any] = {
        'user': user.name if user else None,
        'role': role,
    }

    tag = request.session.get('tag', None)
    logger.debug('Tag config: %s', tag)
    # Filter out non accesible authenticators (using origin)
    authenticators = [
        a
        for a in Authenticator.get_by_tag(
            tag, auth_host if GlobalConfig.DISALLOW_GLOBAL_LOGIN.as_bool(True) else None
        )
        if a.get_instance().is_ip_allowed(request)
    ]

    logger.debug('Authenticators PRE: %s', authenticators)

    use_hidden: bool = tag is not None and tag != 'disabled'
    # No tag, and there are authenticators, let's use the tag of first one
    if not tag and authenticators:  # Keep disabled as tag if present
        tag = authenticators[0].small_name

    # logger.debug('Authenticators: %s', authenticators)

    # the auths for client
    def _get_auth_info(auth: Authenticator) -> dict[str, typing.Any]:
        auth_type = auth.get_type()
        return {
            'id': auth.uuid,
            'name': auth.name,
            'label': auth.small_name,
            'priority': auth.priority,
            'is_custom': auth_type.is_custom(),
        }

    def _is_auth_visible(auth: Authenticator) -> bool:
        """
        Check if the authenticator is visible for the current request.
        This is used to filter out authenticators that are not allowed
        for the current user or request.
        """
        return auth.type_is_valid() and (
            auth.state == consts.auth.VISIBLE or (auth.state == consts.auth.HIDDEN and use_hidden)
        )

    config: dict[str, typing.Any] = {
        'version': consts.system.VERSION,
        'version_stamp': consts.system.VERSION_STAMP,
        'language': get_language(),
        'available_languages': [{'id': k, 'name': gettext(v)} for k, v in settings.LANGUAGES],
        'authenticators': [_get_auth_info(auth) for auth in authenticators if _is_auth_visible(auth)],
        'mfa': request.session.get('mfa', None),
        'tag': tag,
        'os': request.os.os.name,
        'image_size': Image.MAX_IMAGE_SIZE,
        'experimental_features': GlobalConfig.EXPERIMENTAL_FEATURES.as_bool(),
        'reload_time': GlobalConfig.RELOAD_TIME.as_int(True),
        'site_name': GlobalConfig.SITE_NAME.get(),
        'site_copyright_info': GlobalConfig.SITE_COPYRIGHT.get(),
        'site_copyright_link': GlobalConfig.SITE_COPYRIGHT_LINK.get(),
        'site_logo_name': GlobalConfig.SITE_LOGO_NAME.get(),
        'site_information': GlobalConfig.SITE_INFO.get(),
        'site_filter_on_top': GlobalConfig.SITE_FILTER_ONTOP.as_bool(True),
        'launcher_wait_time': 5000,
        'cookies_consent': {
            'text': GlobalConfig.COOKIES_CONSENT_TEXT.get(True),
            'enabled': GlobalConfig.COOKIES_CONSENT_ENABLED.as_bool(True),
            'urls': {
                'leave': GlobalConfig.COOKIES_CONSENT_LEAVE_URL.get(True),
                'more': GlobalConfig.COOKIES_CONSENT_MORE_URL.get(True),
            },
        },
        'messages': {
            # Calendar denied message
            'calendar_denied': GlobalConfig.LIMITED_BY_CALENDAR_TEXT.get().strip()
            or gettext('Access limited by calendar')
        },
        'urls': {
            'change_language': reverse('set_language'),
            'login': reverse('page.login'),
            'mfa': reverse('page.mfa'),
            'logout': reverse('page.logout'),
            'user': reverse('page.index'),
            'custom_auth': reverse('uds.web.views.custom_auth', kwargs={'auth_id': ''}),
            'services': reverse('webapi.services'),
            'error': reverse('webapi.error', kwargs={'err': '9999'}),
            'enabler': reverse(
                'webapi.enabler',
                kwargs={'service_id': 'param1', 'transport_id': 'param2'},
            ),
            'status': reverse('webapi.status', kwargs={'service_id': 'param1', 'transport_id': 'param2'}),
            'action': reverse(
                'webapi.action',
                kwargs={'service_id': 'param1', 'action_string': 'param2'},
            ),
            'gallery_image': reverse('webapi.gallery_image', kwargs={'image_id': 'param1'}),
            'transport_icon': reverse('webapi.transport_icon', kwargs={'transport_id': 'param1'}),
            'static': static(''),
            'client_download': reverse('page.client-download'),
            'update_transport_ticket': reverse(
                'webapi.transport.update_transport_ticket',
                kwargs={'ticket_id': 'param1', 'scrambler': 'param2'},
            ),
            # Launcher URL if exists
            'launch': request.session.get('launch', ''),
            'brand': settings.UDSBRAND if hasattr(settings, 'UDSBRAND') else '',
        },
        'min_for_filter': GlobalConfig.SITE_FILTER_MIN.as_int(True),
    }

    info: typing.Optional[dict[str, typing.Any]] = None
    if user and user.is_staff():
        info = {
            'networks': [n.name for n in Network.get_networks_for_ip(request.ip)],
            'transports': [t.name for t in Transport.objects.all() if t.is_ip_allowed(request.ip)],
            'ip': request.ip,
            'ip_proxy': request.ip_proxy,
        }

    plugins = udsclients_info.PLUGINS.copy()
    # We can add here custom downloads with something like this:
    # plugins.append({
    #     'url': 'http://www.google.com/coche.exe',
    #     'description': 'Cliente SPICE for download',  # Text that appears on download
    #     'name': 'Linux', # Can be 'Linux', 'Windows', o 'MacOS'. Sets the icon.
    #     'legacy': False  # True = Gray, False = White
    # })

    actors: list[dict[str, str | bool]] = []

    if user and user.is_staff():  # Add staff things
        # If is admin (informational, REST api checks users privileges anyway...)
        profile['admin'] = True
        # REST auth
        config['auth_token'] = request.session.session_key
        config['auth_header'] = consts.auth.AUTH_TOKEN_HEADER
        # Actors
        actors = [
            {
                'url': reverse('utility.downloader', kwargs={'download_id': key}),
                'name': val.name,
                'description': val.description,
                'legacy': val.legacy,
            }
            for key, val in downloads_manager().downloadables().items()
        ]
        # URLS
        config['urls']['admin'] = reverse('uds.admin.views.index')
        config['urls']['rest'] = reverse('REST', kwargs={'arguments': ''})
        # Admin config
        page_size = GlobalConfig.ADMIN_PAGESIZE.as_int(True)
        vnc_userservices = GlobalConfig.ADMIN_ENABLE_USERSERVICES_VNC.as_bool(True)
        # Fix page size to razonable usable values
        page_size = 10 if page_size < 10 else 100 if page_size > 100 else page_size
        config['admin'] = {
            'page_size': page_size,
            'vnc_userservices': vnc_userservices,
        }

    errors: list[str] = []
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

    # Return as javascript executable code
    return 'var udsData = ' + json.dumps(uds) + ';\n'
