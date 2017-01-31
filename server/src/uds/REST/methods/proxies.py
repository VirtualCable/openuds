# -*- coding: utf-8 -*-

#
# Copyright (c) 2017 Virtual Cable S.L.
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
@itemor: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_lazy as _, ugettext
from uds.models import Proxy
from uds.core.ui.UserInterface import gui
from uds.core.util import permissions
import datetime

from uds.REST.model import ModelHandler

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Proxies(ModelHandler):
    '''
    Processes REST requests about proxys
    '''
    model = Proxy

    save_fields = ['name', 'host', 'port', 'ssl', 'check_cert', 'comments', 'tags']

    table_title = _('Proxies')
    table_fields = [
        {'name': {'title': _('Name'), 'visible': True}},
        {'url': {'title': _('Server'), 'visible': True}},
        {'check_cert': {'title': _('Check certificate'), 'visible': True}},
        {'comments': {'title': _('Comments')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def item_as_dict(self, proxy):
        return {
            'id': proxy.uuid,
            'name': proxy.name,
            'tags': [tag.tag for tag in proxy.tags.all()],
            'comments': proxy.comments,
            'url': proxy.url,
            'host': proxy.host,
            'port': proxy.port,
            'ssl': proxy.ssl,
            'check_cert': proxy.check_cert,
            'permission': permissions.getEffectivePermission(self._user, proxy)
        }

    def getGui(self, type_):
        g = self.addDefaultFields([], ['name', 'comments', 'tags'])

        for f in [{
            'name': 'host',
            'value': '',
            'label': ugettext('Host'),
            'tooltip': ugettext('Server (IP or FQDN) that will serve as proxy.'),
            'type': gui.InputField.TEXT_TYPE,
            'order': 110,
        }, {
            'name': 'port',
            'value': '9090',
            'minValue': '0',
            'label': ugettext('Port'),
            'tooltip': ugettext('Port of proxy server'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 111,
        }, {
            'name': 'ssl',
            'value': True,
            'label': ugettext('Use SSL'),
            'tooltip': ugettext('If active, the proxied connections will be done using HTTPS'),
            'type': gui.InputField.CHECKBOX_TYPE,
        }, {
            'name': 'check_cert',
            'value': True,
            'label': ugettext('Check Certificate'),
            'tooltip': ugettext('If active, any SSL certificate will be checked (will not allow self signed certificates on proxy)'),
            'type': gui.InputField.CHECKBOX_TYPE,
        },
        ]:
            self.addField(g, f)

        return g
