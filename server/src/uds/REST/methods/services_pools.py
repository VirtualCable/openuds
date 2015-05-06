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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext, ugettext_lazy as _
from uds.models import DeployedService, OSManager, Service, Image
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.State import State
from uds.core.util import log
from uds.core.util import permissions
from uds.REST.model import ModelHandler
from uds.REST import RequestError, ResponseError
from uds.core.ui.UserInterface import gui
from .user_services import AssignedService, CachedService, Groups, Transports, Publications
from .services import Services

import logging

logger = logging.getLogger(__name__)


class ServicesPools(ModelHandler):
    '''
    Handles Services Pools REST requests
    '''
    model = DeployedService
    detail = {
        'services': AssignedService,
        'cache': CachedService,
        'groups': Groups,
        'transports': Transports,
        'publications': Publications,
    }

    save_fields = ['name', 'comments', 'service_id', 'osmanager_id', 'image_id', 'initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs', 'show_transports']
    remove_fields = ['osmanager_id', 'service_id']

    table_title = _('Service Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'parent': {'title': _('Parent Service')}},  # Will process this field on client in fact, not sent by server
        {'state': {'title': _('status'), 'type': 'dict', 'dict': State.dictionary()}},
        {'show_transports': {'title': _('Shows transports')}},  # Will process this field on client in fact, not sent by server
        {'comments': {'title': _('Comments')}},
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = {'field': 'state', 'prefix': 'row-state-'}

    def item_as_dict(self, item):
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped
        val = {
            'id': item.uuid,
            'name': item.name,
            'parent': item.service.name,
            'parent_type': item.service.data_type,
            'comments': item.comments,
            'state': item.state if item.service.provider.maintenance_mode is False else State.MAINTENANCE,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'service_id': item.service.uuid,
            'provider_id': item.service.provider.uuid,
            'image_id': item.image.uuid if item.image is not None else None,
            'initial_srvs': item.initial_srvs,
            'cache_l1_srvs': item.cache_l1_srvs,
            'cache_l2_srvs': item.cache_l2_srvs,
            'max_srvs': item.max_srvs,
            'user_services_count': item.userServices.count(),
            'restrained': item.isRestrained(),
            'show_transports': item.show_transports,
            'permission': permissions.getEffectivePermission(self._user, item),
            'info': Services.serviceInfo(item.service),
        }

        if item.osmanager is not None:
            val['osmanager_id'] = item.osmanager.uuid

        return val

    # Gui related
    def getGui(self, type_):
        if OSManager.objects.count() < 1:  # No os managers, can't create db
            raise ResponseError(ugettext('Create at least one OS Manager before creating a new service pool'))
        if Service.objects.count() < 1:
            raise ResponseError(ugettext('Create at least a service before creating a new service pool'))

        g = self.addDefaultFields([], ['name', 'comments'])

        for f in [{
            'name': 'service_id',
            'values': [gui.choiceItem(-1, '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.provider.name + '\\' + v.name) for v in Service.objects.all()]),
            'label': ugettext('Base service'),
            'tooltip': ugettext('Service used as base of this service pool'),
            'type': gui.InputField.CHOICE_TYPE,
            'rdonly': True,
            'order': 100,  # Ensueres is At end
        }, {
            'name': 'osmanager_id',
            'values': [gui.choiceItem(-1, '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.name) for v in OSManager.objects.all()]),
            'label': ugettext('OS Manager'),
            'tooltip': ugettext('OS Manager used as base of this service pool'),
            'type': gui.InputField.CHOICE_TYPE,
            'rdonly': True,
            'order': 101,
        }, {
            'name': 'image_id',
            'values': [gui.choiceItem(-1, '')] + gui.sortedChoices([gui.choiceItem(v.uuid, v.name) for v in Image.objects.all()]),
            'label': ugettext('Associated Image'),
            'tooltip': ugettext('Image assocciated with this service'),
            'type': gui.InputField.CHOICE_TYPE,
            'order': 102,
        }, {
            'name': 'initial_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Initial available services'),
            'tooltip': ugettext('Services created initially for this service pool'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 103,
        }, {
            'name': 'cache_l1_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Services to keep in cache'),
            'tooltip': ugettext('Services kept in cache for improved user service assignation'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 104,
        }, {
            'name': 'cache_l2_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Services to keep in L2 cache'),
            'tooltip': ugettext('Services kept in cache of level2 for improved service generation'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 105,
        }, {
            'name': 'max_srvs',
            'value': '0',
            'minValue': '1',
            'label': ugettext('Maximum number of services to provide'),
            'tooltip': ugettext('Maximum number of service (assigned and L1 cache) that can be created for this service'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 106,
        }, {
            'name': 'show_transports',
            'value': True,
            'label': ugettext('Show transports'),
            'tooltip': ugettext('If active, alternative transports for user will be shown'),
            'type': gui.InputField.CHECKBOX_TYPE,
            'order': 107,
        }]:
            self.addField(g, f)

        return g

    def beforeSave(self, fields):
        # logger.debug(self._params)
        try:
            try:
                service = Service.objects.get(uuid=fields['service_id'])
                fields['service_id'] = service.id
            except:
                raise RequestError(ugettext('Base service does not exist anymore'))

            try:
                serviceType = service.getType()

                if serviceType.publicationType is None:
                    self._params['publish_on_save'] = False

                if serviceType.needsManager is True:
                    osmanager = OSManager.objects.get(uuid=fields['osmanager_id'])
                    fields['osmanager_id'] = osmanager.id
                else:
                    del fields['osmanager_id']

                if serviceType.usesCache is False:
                    for k in ('initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs'):
                        fields[k] = 0

            except Exception:
                raise RequestError(ugettext('This service requires an OS Manager'))

            imgId = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: {}'.format(imgId))
            try:
                if imgId != '-1':
                    image = Image.objects.get(uuid=imgId)
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

        except (RequestError, ResponseError):
            raise
        except Exception as e:
            raise RequestError(str(e))

    def afterSave(self, item):
        if self._params.get('publish_on_save', False) is True:
            item.publish()

    def deleteItem(self, item):
        item.remove()  # This will mark it for deletion, but in fact will not delete it directly

    # Logs
    def getLogs(self, item):
        return log.getLogs(item)
