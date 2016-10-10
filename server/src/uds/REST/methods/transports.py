# -*- coding: utf-8 -*-

#
# Copyright (c) 2014 Virtual Cable S.L.
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
from uds.models import Transport, Network
from uds.core.transports import factory
from uds.core.util import permissions
from uds.core.util import OsDetector

from uds.REST.model import ModelHandler

import logging

logger = logging.getLogger(__name__)

# Enclosed methods under /item path


class Transports(ModelHandler):
    model = Transport
    save_fields = ['name', 'comments', 'tags', 'priority', 'nets_positive', 'allowed_oss']

    table_title = _('Current Transports')
    table_fields = [
        {'priority': {'title': _('Priority'), 'type': 'numeric', 'width': '6em'}},
        {'name': {'title': _('Name'), 'visible': True, 'type': 'iconType'}},
        {'comments': {'title': _('Comments')}},
        {'allowed_oss': {'title': _('Devices'), 'width': '8em'}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]

    def enum_types(self):
        return factory().providers().values()

    def getGui(self, type_):
        try:
            return self.addField(
                    self.addField(
                        self.addField(self.addDefaultFields(factory().lookup(type_).guiDescription(), ['name', 'comments', 'tags', 'priority']), {
                            'name': 'nets_positive',
                            'value': True,
                            'label': ugettext('Network access'),
                            'tooltip': ugettext('If checked, the transport will be enabled for the selected networks.If unchecked, transport will be disabled for selected networks'),
                            'type': 'checkbox',
                            'order': 100,  # At end
                        }), {
                        'name': 'networks',
                        'value': [],
                        'values': sorted([{'id': x.id, 'text': x.name} for x in Network.objects.all()], key=lambda x: x['text'].lower()),  # TODO: We will fix this behavior after current admin client is fully removed
                        'label': ugettext('Networks'),
                        'tooltip': ugettext('Networks associated with this transport. If No network selected, will mean "all networks"'),
                        'type': 'multichoice',
                        'order': 101
                    }), {
                    'name': 'allowed_oss',
                    'value': [],
                    'values': sorted([{'id': x, 'text': x} for x in OsDetector.knownOss], key=lambda x: x['text'].lower()),  # TODO: We will fix this behavior after current admin client is fully removed
                    'label': ugettext('Allowed Devices'),
                    'tooltip': ugettext('If empty, any kind of device compatible with this transport will be allowed. Else, only devices compatible with selected values will be allowed'),
                    'type': 'multichoice',
                    'order': 102
                })

        except Exception:
            self.invalidItemException()

    def item_as_dict(self, item):
        type_ = item.getType()
        return {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'comments': item.comments,
            'priority': item.priority,
            'nets_positive': item.nets_positive,
            'networks': [{'id': n.id} for n in item.networks.all()],
            'allowed_oss': [{'id': x} for x in item.allowed_oss.split(',')] if item.allowed_oss != '' else [],
            'deployed_count': item.deployedServices.count(),
            'type': type_.type(),
            'protocol': type_.protocol,
            'permission': permissions.getEffectivePermission(self._user, item)
        }

    def beforeSave(self, fields):
        fields['allowed_oss'] = ','.join(fields['allowed_oss'])


    def afterSave(self, item):
        try:
            networks = self._params['networks']
        except:  # No networks passed in, this is ok
            logger.debug('No networks')
            return
        if networks is None:
            return
        logger.debug('Networks: {0}'.format(networks))
        item.networks = Network.objects.filter(id__in=networks)

        # try:
        #    oss = ','.join(self._params['allowed_oss'])
        # except:
        #    oss = ''
        # logger.debug('Devices: {0}'.format(oss))
        # item.allowed_oss = oss
        # item.save()  # Store correctly the allowed_oss
