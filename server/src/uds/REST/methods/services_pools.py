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
from uds.models import DeployedService, OSManager, Service, Image, ServicesPoolGroup
from uds.models.CalendarAction import CALENDAR_ACTION_INITIAL, CALENDAR_ACTION_MAX, CALENDAR_ACTION_CACHE_L1, CALENDAR_ACTION_CACHE_L2, CALENDAR_ACTION_PUBLISH
from uds.core.ui.images import DEFAULT_THUMB_BASE64
from uds.core.util.State import State
from uds.core.util.model import processUuid
from uds.core.util import log
from uds.core.util import permissions
from uds.REST.model import ModelHandler
from uds.REST import RequestError, ResponseError
from uds.core.ui.UserInterface import gui
from .user_services import AssignedService, CachedService, Groups, Transports, Publications, Changelog
from .services_pool_calendars import AccessCalendars, ActionsCalendars
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
        'changelog': Changelog,
        'access': AccessCalendars,
        'actions': ActionsCalendars
    }

    save_fields = ['name', 'comments', 'tags', 'service_id', 'osmanager_id', 'image_id', 'servicesPoolGroup_id', 'initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs', 'show_transports']
    remove_fields = ['osmanager_id', 'service_id']

    table_title = _('Service Pools')
    table_fields = [
        {'name': {'title': _('Name')}},
        {'parent': {'title': _('Parent Service')}},
        {'state': {'title': _('status'), 'type': 'dict', 'dict': State.dictionary()}},
        {'show_transports': {'title': _('Shows transports'), 'type': 'callback'}},
        {'pool_group_name': {'title': _('Pool Group')}},
        {'tags': {'title': _('tags'), 'visible': False}},
    ]
    # Field from where to get "class" and prefix for that class, so this will generate "row-state-A, row-state-X, ....
    table_row_style = {'field': 'state', 'prefix': 'row-state-'}

    custom_methods = [('setFallbackAccess', True), ('actionsList', True)]


    def item_as_dict(self, item):
        # if item does not have an associated service, hide it (the case, for example, for a removed service)
        # Access from dict will raise an exception, and item will be skipped
        poolGroupId = None
        poolGroupName = _('Default')
        poolGroupThumb = DEFAULT_THUMB_BASE64
        if item.servicesPoolGroup is not None:
            poolGroupId = item.servicesPoolGroup.uuid
            poolGroupName = item.servicesPoolGroup.name
            if item.servicesPoolGroup.image is not None:
                poolGroupThumb = item.servicesPoolGroup.image.thumb64
        val = {
            'id': item.uuid,
            'name': item.name,
            'tags': [tag.tag for tag in item.tags.all()],
            'parent': item.service.name,
            'parent_type': item.service.data_type,
            'comments': item.comments,
            'state': item.state if item.isInMaintenance() is False else State.MAINTENANCE,
            'thumb': item.image.thumb64 if item.image is not None else DEFAULT_THUMB_BASE64,
            'service_id': item.service.uuid,
            'provider_id': item.service.provider.uuid,
            'image_id': item.image.uuid if item.image is not None else None,
            'pool_group_id': poolGroupId,
            'pool_group_name': poolGroupName,
            'pool_group_thumb': poolGroupThumb,
            'initial_srvs': item.initial_srvs,
            'cache_l1_srvs': item.cache_l1_srvs,
            'cache_l2_srvs': item.cache_l2_srvs,
            'max_srvs': item.max_srvs,
            'user_services_count': item.userServices.count(),
            'restrained': item.isRestrained(),
            'show_transports': item.show_transports,
            'fallbackAccess': item.fallbackAccess,
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

        g = self.addDefaultFields([], ['name', 'comments', 'tags'])

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
            'values': [gui.choiceImage(-1, '--------', DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.thumb64) for v in Image.objects.all()]),
            'label': ugettext('Associated Image'),
            'tooltip': ugettext('Image assocciated with this service'),
            'type': gui.InputField.IMAGECHOICE_TYPE,
            'order': 102,
            'tab': ugettext('Display'),
        }, {
            'name': 'servicesPoolGroup_id',
            'values': [gui.choiceImage(-1, _('Default'), DEFAULT_THUMB_BASE64)] + gui.sortedChoices([gui.choiceImage(v.uuid, v.name, v.image.thumb64) for v in ServicesPoolGroup.objects.all()]),
            'label': ugettext('Pool group'),
            'tooltip': ugettext('Pool group for this pool (for pool clasify on display)'),
            'type': gui.InputField.IMAGECHOICE_TYPE,
            'order': 103,
            'tab': ugettext('Display'),
        }, {
            'name': 'initial_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Initial available services'),
            'tooltip': ugettext('Services created initially for this service pool'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 110,
            'tab': ugettext('Availability'),
        }, {
            'name': 'cache_l1_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Services to keep in cache'),
            'tooltip': ugettext('Services kept in cache for improved user service assignation'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 111,
            'tab': ugettext('Availability'),
        }, {
            'name': 'cache_l2_srvs',
            'value': '0',
            'minValue': '0',
            'label': ugettext('Services to keep in L2 cache'),
            'tooltip': ugettext('Services kept in cache of level2 for improved service generation'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 112,
            'tab': ugettext('Availability'),
        }, {
            'name': 'max_srvs',
            'value': '0',
            'minValue': '1',
            'label': ugettext('Maximum number of services to provide'),
            'tooltip': ugettext('Maximum number of service (assigned and L1 cache) that can be created for this service'),
            'type': gui.InputField.NUMERIC_TYPE,
            'order': 113,
            'tab': ugettext('Availability'),
        }, {
            'name': 'show_transports',
            'value': True,
            'label': ugettext('Show transports'),
            'tooltip': ugettext('If active, alternative transports for user will be shown'),
            'type': gui.InputField.CHECKBOX_TYPE,
            'order': 120,
        }]:
            self.addField(g, f)

        return g

    def beforeSave(self, fields):
        # logger.debug(self._params)
        try:
            try:
                service = Service.objects.get(uuid=processUuid(fields['service_id']))
                fields['service_id'] = service.id
            except:
                raise RequestError(ugettext('Base service does not exist anymore'))

            try:
                serviceType = service.getType()

                if serviceType.publicationType is None:
                    self._params['publish_on_save'] = False

                if serviceType.needsManager is True:
                    osmanager = OSManager.objects.get(uuid=processUuid(fields['osmanager_id']))
                    fields['osmanager_id'] = osmanager.id
                else:
                    del fields['osmanager_id']

                if serviceType.usesCache is False:
                    for k in ('initial_srvs', 'cache_l1_srvs', 'cache_l2_srvs', 'max_srvs'):
                        fields[k] = 0

            except Exception:
                raise RequestError(ugettext('This service requires an OS Manager'))

            # If max < initial or cache_1 or cache_l2
            fields['max_srvs'] = max((int(fields['initial_srvs']), int(fields['cache_l1_srvs']), int(fields['max_srvs'])))

            imgId = fields['image_id']
            fields['image_id'] = None
            logger.debug('Image id: {}'.format(imgId))
            try:
                if imgId != '-1':
                    image = Image.objects.get(uuid=processUuid(imgId))
                    fields['image_id'] = image.id
            except Exception:
                logger.exception('At image recovering')

            # Servicepool Group
            spgrpId = fields['servicesPoolGroup_id']
            fields['servicesPoolGroup_id'] = None
            logger.debug('servicesPoolGroup_id: {}'.format(spgrpId))
            try:
                if imgId != '-1':
                    spgrp = ServicesPoolGroup.objects.get(uuid=processUuid(spgrpId))
                    fields['servicesPoolGroup_id'] = spgrp.id
            except Exception:
                logger.exception('At service pool group recovering')

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
        try:
            return log.getLogs(item)
        except Exception:
            return []

    # Set fallback status
    def setFallbackAccess(self, item):
        self.ensureAccess(item, permissions.PERMISSION_MANAGEMENT)

        fallback = self._params.get('fallbackAccess')
        logger.debug('Setting fallback of {} to {}'.format(item.name, fallback))
        item.fallbackAccess = fallback
        item.save()
        return ''

    #  Returns the action list based on current element, for calendar
    def actionsList(self, item):
        validActions = ()
        itemInfo = item.service.getType()
        if itemInfo.usesCache is True:
            validActions += (CALENDAR_ACTION_INITIAL, CALENDAR_ACTION_CACHE_L1, CALENDAR_ACTION_MAX)
            if itemInfo.usesCache_L2 is True:
                validActions += (CALENDAR_ACTION_CACHE_L2,)

        if itemInfo.publicationType is not None:
            validActions += (CALENDAR_ACTION_PUBLISH,)

        return validActions
